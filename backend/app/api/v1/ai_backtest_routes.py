"""AI 回测 API 路由。"""

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_pagination
from app.core.database import redis_client
from app.models.user import User
from app.schemas.ai_backtest import (
    AIBacktestCreate,
    AIBacktestProgress,
    MergeOptimizeRequest,
)
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.services.ai_backtest_service import AIBacktestService

router = APIRouter(prefix="/strategies/ai-backtest", tags=["AI 回测"])


@router.post("", summary="创建并启动 AI 回测", status_code=201)
async def create_ai_backtest(
    data: AIBacktestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建并启动 AI 驱动回测。"""
    service = AIBacktestService(db)
    result = await service.create_backtest(current_user.id, data)
    return ApiResponse(data=result)


@router.get("/list", summary="获取 AI 回测历史列表")
async def list_ai_backtests(
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户的历史 AI 回测列表。"""
    service = AIBacktestService(db)
    items, total = await service.list_history(
        current_user.id, pagination.page, pagination.page_size
    )
    return ApiResponse(
        data=PaginatedResponse(
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            items=items,
        )
    )


@router.get("/{backtest_id}", summary="获取 AI 回测详情")
async def get_ai_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 AI 回测详情（含总结指标）。"""
    service = AIBacktestService(db)
    result = await service.get_backtest(backtest_id, current_user.id)
    return ApiResponse(data=result)


@router.get("/{backtest_id}/trades", summary="获取交易明细")
async def list_ai_backtest_trades(
    backtest_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 AI 回测的交易明细列表。"""
    service = AIBacktestService(db)
    items, total = await service.get_trades(
        backtest_id, current_user.id, page, page_size
    )
    return ApiResponse(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )
    )


@router.get("/{backtest_id}/progress", summary="SSE 回测进度推送")
async def get_ai_backtest_progress(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE 流式推送回测进度。

    重要设计（解决浏览器一直 pending 的问题）：
    1. 无论回测状态如何，都先从 Redis 缓存读取最新进度并立即推送
    2. 运行中的回测：先推缓存快照，再订阅实时推送
    3. 已完成/失败/取消的回测：推缓存 + 数据库数据，立即关闭
    4. 每 15 秒发送心跳，防止连接超时
    5. 5 分钟无数据自动关闭连接
    """
    service = AIBacktestService(db)
    await service._verify_ownership(backtest_id, current_user.id)

    bt_id = str(backtest_id)

    async def _read_cached():
        """从 Redis 读取最新缓存进度。"""
        if redis_client is None:
            return None
        try:
            last_key = f"ai-backtest-last-progress:{bt_id}"
            last_data = await redis_client.get(last_key)
            if last_data:
                return json.loads(last_data)
        except Exception:
            pass
        return None

    async def event_generator():
        if redis_client is None:
            yield f"data: {json.dumps({'error': 'Redis 不可用'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        backtest = await service.get_backtest(backtest_id, current_user.id)
        stage_map = {
            "completed": "done", "failed": "error",
            "cancelled": "cancelled", "running": "running",
            "pending": "pending",
        }

        # == 1. 先推缓存快照（无论回测状态如何） ==
        cached = await _read_cached()
        if cached:
            # 从缓存补充 db 字段（ai_analysis_logs, initial_analysis 等）
            cached["ai_analysis_logs"] = getattr(backtest, "ai_analysis_logs", [])
            if backtest.initial_analysis:
                cached["initial_analysis"] = backtest.initial_analysis
            yield f"data: {json.dumps(cached, ensure_ascii=False)}\n\n"
            # 如果缓存已经是终态，直接关闭
            if cached.get("stage") in ("done", "error", "cancelled"):
                yield "data: [DONE]\n\n"
                return

        # == 2. 如果回测已终态，补推数据库完整数据并关闭 ==
        if backtest.status in ("completed", "failed", "cancelled"):
            payload = {
                "backtest_id": bt_id,
                "stage": stage_map.get(backtest.status, "error"),
                "progress": backtest.progress,
                "current_kline": backtest.completed_klines,
                "total_klines": backtest.total_klines,
                "current_trades": 0,
                "message": "回测已" + (
                    "完成" if backtest.status == "completed" else
                    "失败" if backtest.status == "failed" else
                    "取消"
                ),
                "precheck_total": backtest.precheck_total,
                "precheck_triggered": backtest.precheck_triggered,
                "ai_call_count": backtest.ai_call_count,
                "current_stage_detail": "",
                "initial_analysis": backtest.initial_analysis,
                "ai_analysis_logs": backtest.ai_analysis_logs,
                "key_levels": (backtest.initial_analysis or {}).get("key_levels", []),
                "has_position": False,
            }
            # 如果缓存中有 ai_analysis 和 indicators，补进去
            if cached:
                if cached.get("ai_analysis"):
                    payload["ai_analysis"] = cached["ai_analysis"]
                if cached.get("indicators"):
                    payload["indicators"] = cached["indicators"]
                if cached.get("close_price"):
                    payload["close_price"] = cached["close_price"]
            else:
                # 没有缓存，尝试从 Redis 读
                _c = await _read_cached()
                if _c:
                    if _c.get("ai_analysis"):
                        payload["ai_analysis"] = _c["ai_analysis"]
                    if _c.get("indicators"):
                        payload["indicators"] = _c["indicators"]
                    if _c.get("close_price"):
                        payload["close_price"] = _c["close_price"]
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # == 2.5 待开始回测：推数据库状态并关闭，不等待 ==
        if backtest.status == "pending":
            payload = {
                "backtest_id": bt_id,
                "stage": "pending",
                "progress": 0,
                "current_kline": 0,
                "total_klines": backtest.total_klines,
                "current_trades": 0,
                "message": "回测正在排队等待执行，请稍候...",
                "precheck_total": 0,
                "precheck_triggered": 0,
                "ai_call_count": 0,
                "current_stage_detail": "",
                "initial_analysis": None,
                "ai_analysis_logs": [],
                "key_levels": [],
                "has_position": False,
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # == 3. 运行中：订阅实时推送 + 心跳 ==
        pubsub = redis_client.pubsub()
        channel = f"ai-backtest-progress:{bt_id}"
        await pubsub.subscribe(channel)

        try:
            start = asyncio.get_event_loop().time()
            timeout = 300  # 5 分钟无新数据自动关闭
            last_heartbeat = start
            while True:
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed > timeout:
                    break

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg is None:
                    # 心跳：每 15 秒发送一次，保持连接活跃
                    now = asyncio.get_event_loop().time()
                    if now - last_heartbeat >= 15:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now
                    continue

                if msg.get("type") == "message":
                    yield f"data: {msg.get('data')}\n\n"
                    last_heartbeat = asyncio.get_event_loop().time()
                    try:
                        payload = json.loads(msg.get("data"))
                        if payload.get("stage") in ("done", "error", "cancelled"):
                            break
                    except Exception:
                        pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/{backtest_id}/cancel", summary="取消 AI 回测")
async def cancel_ai_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消待开始的 AI 回测。"""
    service = AIBacktestService(db)
    await service.cancel_backtest(backtest_id, current_user.id)
    return ApiResponse(data={"status": "cancelled"})


@router.post("/{backtest_id}/stop", summary="终止运行中的 AI 回测")
async def stop_ai_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """终止正在运行的 AI 回测。

    1. 验证所有权 + 状态为 running
    2. 设置 Redis 停止标志 (TTL 3600s)
    3. 更新 DB 状态为 cancelling
    4. 返回 {status: "stopping"}
    """
    service = AIBacktestService(db)
    await service.stop_backtest(backtest_id, current_user.id)
    return ApiResponse(data={"status": "stopping"})


@router.delete("/{backtest_id}", summary="删除 AI 回测记录")
async def delete_ai_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 AI 回测记录（含交易明细、分析日志和 Redis 缓存）。

    仅支持删除已完成的回测（completed / cancelled / failed）。
    """
    service = AIBacktestService(db)
    await service.delete_backtest(backtest_id, current_user.id)
    return ApiResponse(data={"status": "deleted"})


@router.post("/{backtest_id}/analyze", summary="AI 分析回测结果")
async def analyze_ai_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对已完成的回测进行 AI 分析。

    1. 验证所有权 + 状态为 completed
    2. 读取回测结果摘要 + 所有交易明细 + 策略规则
    3. 调用 LLM 进行分析
    4. 保存分析结果到 backtest.result_summary.ai_analysis
    5. 返回分析结果
    """
    service = AIBacktestService(db)
    result = await service.analyze_results(backtest_id, current_user.id)
    return ApiResponse(data=result)


@router.post("/{backtest_id}/optimize", summary="基于回测结果优化策略")
async def optimize_strategy(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于回测结果生成新的优化策略。

    1. 验证所有权 + 状态为 completed
    2. 读取回测结果 + 已有 AI 分析 + 原策略规则
    3. 调用 LLM 生成优化后的策略规则
    4. 创建新策略记录 (名称: "原策略名 - 优化版 vN")
    5. 在新策略 extra 记录 source_backtest_id
    6. 返回新策略详情
    """
    service = AIBacktestService(db)
    result = await service.optimize_strategy(backtest_id, current_user.id)
    return ApiResponse(data=result)


@router.post("/{backtest_id}/merge-optimize", summary="多策略融合优化")
async def merge_optimize(
    backtest_id: uuid.UUID,
    data: MergeOptimizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """多策略融合优化：基于多个策略的回测结果生成融合后的新策略。

    1. 验证所有策略存在且属于当前用户
    2. 验证父回测已完成
    3. 调用 LLM 分析各策略表现，生成融合规则
    4. 创建新策略 + 子回测并启动
    """
    # 确保请求中的 backtest_id 与路径参数一致
    data.backtest_id = backtest_id
    service = AIBacktestService(db)
    result = await service.merge_optimize(current_user.id, data)
    return ApiResponse(data=result)