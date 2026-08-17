"""后台任务管理 API 路由。

查询排队/运行中的 Celery 任务信息，支持取消和终止任务。
"""

import base64
import json
import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.database import redis_client
from app.models.ai_backtest import AIBacktest
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/tasks", tags=["系统管理 - 后台任务"])


class CeleryTaskInfo:
    """Celery 任务信息解析结果。"""

    task_id: str
    task_name: str
    queue_name: str
    received_at: Optional[datetime]
    eta: Optional[datetime]

    def __init__(
        self,
        task_id: str,
        task_name: str,
        queue_name: str,
        received_at: Optional[datetime] = None,
        eta: Optional[datetime] = None,
    ):
        self.task_id = task_id
        self.task_name = task_name
        self.queue_name = queue_name
        self.received_at = received_at
        self.eta = eta

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "queue_name": self.queue_name,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "eta": self.eta.isoformat() if self.eta else None,
        }


def parse_celery_message(raw: str, queue_name: str) -> Optional[CeleryTaskInfo]:
    """解析 Celery Redis 队列消息，提取任务信息。"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    # Celery 消息格式：{"body": "base64...", "headers": {"id": "...", "task": "...", ...}}
    headers = data.get("headers", {})
    task_id = headers.get("id")
    task_name = headers.get("task")

    if not task_id or not task_name:
        return None

    # 解析 eta 时间
    eta: Optional[datetime] = None
    if "eta" in headers and headers["eta"]:
        try:
            eta = datetime.fromisoformat(headers["eta"])
        except (ValueError, TypeError):
            pass

    return CeleryTaskInfo(
        task_id=task_id,
        task_name=task_name,
        queue_name=queue_name,
        eta=eta,
    )


@router.get("/queued", summary="获取排队中和运行中的任务列表")
async def list_queued_tasks(
    task_name_filter: Optional[str] = Query(None, description="按任务名称筛选"),
):
    """列出所有 Redis 队列中排队的任务。

    因为 Celery concurrency=1，一次只能处理一个任务，其他都在队列中排队。
    """
    queues = ["default", "celery"]
    result: List[CeleryTaskInfo] = []

    if redis_client is None:
        return ApiResponse(
            data={"tasks": [], "total": 0},
            message="Redis 未连接",
        )

    for queue in queues:
        length = await redis_client.llen(queue)
        if length == 0:
            continue

        # 遍历队列中所有任务
        for i in range(length):
            raw = await redis_client.lindex(queue, i)
            if not raw:
                continue
            info = parse_celery_message(raw, queue)
            if not info:
                continue

            # 筛选
            if task_name_filter:
                if task_name_filter.lower() not in info.task_name.lower():
                    continue

            result.append(info)

    # 按队列顺序返回
    response_data = [t.to_dict() for t in result]
    return ApiResponse(data={
        "tasks": response_data,
        "total": len(response_data),
    })


@router.delete("/queued/{task_id}", summary="从队列中删除排队的任务")
async def delete_queued_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """从 Redis 队列中删除一个排队的任务。

    只能删除排队中的任务，无法删除正在执行的任务。
    正在执行的任务需要设置停止标记（针对可中断任务如 AI 回测）。

    如果任务是 AI 回测，同时将其状态更新为 cancelled。
    """
    if redis_client is None:
        return ApiResponse(message="Redis 未连接", code=1)

    queues = ["default", "celery"]
    deleted = False
    deleted_backtest_id: Optional[uuid.UUID] = None

    for queue in queues:
        length = await redis_client.llen(queue)
        if length == 0:
            continue

        # 遍历队列查找任务
        for i in range(length):
            raw = await redis_client.lindex(queue, i)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                headers = data.get("headers", {})
                if headers.get("id") == task_id:
                    # 检查是否是 run_ai_backtest，尝试提取 backtest_id
                    task_name = headers.get("task")
                    if task_name == "app.tasks.ai_backtest_tasks.run_ai_backtest":
                        # 解码 body 提取 backtest_id
                        try:
                            body_b64 = data.get("body", "")
                            if body_b64:
                                body_json = base64.b64decode(body_b64).decode("utf-8")
                                body_data = json.loads(body_json)
                                # body_data 是 {"args": [...]}
                                if body_data.get("args") and len(body_data["args"]) > 0:
                                    backtest_id_str = body_data["args"][0]
                                    try:
                                        deleted_backtest_id = uuid.UUID(backtest_id_str)
                                    except ValueError:
                                        pass
                        except Exception:
                            pass

                    # 使用 LREM 删除这个元素（count=1 只删第一个匹配的）
                    await redis_client.lrem(queue, 1, raw)
                    deleted = True
                    break
            except json.JSONDecodeError:
                continue

        if deleted:
            break

    if not deleted:
        return ApiResponse(message=f"在队列中未找到任务 {task_id}", code=1)

    # 如果是 AI 回测，更新数据库状态为 cancelled
    if deleted_backtest_id:
        result = await db.execute(
            select(AIBacktest).where(AIBacktest.id == deleted_backtest_id)
        )
        backtest = result.scalar_one_or_none()
        if backtest:
            backtest.status = "cancelled"
            backtest.completed_at = datetime.now()
            await db.commit()

    return ApiResponse(message=f"已删除排队任务 {task_id}")


@router.post("/cancel-running/ai-backtest/{backtest_id}", summary="终止正在运行的 AI 回测")
async def cancel_running_ai_backtest(backtest_id: str, db: AsyncSession = Depends(get_db)):
    """终止一个正在运行的 AI 回测任务。

    设置停止标记，任务会在下一个检查点主动停止。
    同时更新数据库状态为 cancelled。
    """
    if redis_client is None:
        return ApiResponse(message="Redis 未连接", code=1)

    # 设置停止标记，和 /cancel 端点逻辑一致
    stop_key = f"stop:ai-backtest:{backtest_id}"
    await redis_client.setex(stop_key, 86400, "1")

    # 同时清理进度缓存
    progress_key = f"ai-backtest-last-progress:{backtest_id}"
    await redis_client.delete(progress_key)

    # 更新数据库状态为 cancelled
    try:
        bt_uuid = uuid.UUID(backtest_id)
        result = await db.execute(
            select(AIBacktest).where(AIBacktest.id == bt_uuid)
        )
        backtest = result.scalar_one_or_none()
        if backtest and backtest.status == "running":
            backtest.status = "cancelled"
            backtest.completed_at = datetime.now()
            await db.commit()
    except (ValueError, Exception):
        pass

    return ApiResponse(message=f"已发送停止信号到 AI 回测 {backtest_id}")


@router.get("/info", summary="获取队列统计信息")
async def get_queue_stats():
    """获取各队列长度统计。"""
    if redis_client is None:
        return ApiResponse(data={
            "redis_connected": False,
            "queues": {},
        })

    queues = ["default", "celery"]
    stats = {}
    for q in queues:
        stats[q] = await redis_client.llen(q)

    return ApiResponse(data={
        "redis_connected": True,
        "queues": stats,
    })