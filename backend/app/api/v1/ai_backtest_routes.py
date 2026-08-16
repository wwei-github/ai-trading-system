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
    """SSE 流式推送回测进度。"""
    # 验证所有权
    service = AIBacktestService(db)
    await service._verify_ownership(backtest_id, current_user.id)

    bt_id = str(backtest_id)

    async def event_generator():
        if redis_client is None:
            yield f"data: {json.dumps({'error': 'Redis 不可用'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 先推送当前状态
        backtest = await service.get_backtest(backtest_id, current_user.id)
        if backtest.status in ("completed", "failed", "cancelled"):
            stage_map = {
                "completed": "done",
                "failed": "error",
                "cancelled": "cancelled",
            }
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
                # 08-AI回测K线分析优化 新增字段
                "precheck_total": backtest.precheck_total,
                "precheck_triggered": backtest.precheck_triggered,
                "ai_call_count": backtest.ai_call_count,
                "current_stage_detail": "",
                "initial_analysis": backtest.initial_analysis,
                "ai_analysis_logs": backtest.ai_analysis_logs,
            }
            # 尝试从 Redis 读取最后一次推送的进度数据（包含 ai_analysis 和 indicators）
            try:
                last_key = f"ai-backtest-last-progress:{bt_id}"
                last_data = await redis_client.get(last_key)
                if last_data:
                    last = json.loads(last_data)
                    if last.get("ai_analysis"):
                        payload["ai_analysis"] = last["ai_analysis"]
                    if last.get("indicators"):
                        payload["indicators"] = last["indicators"]
            except Exception:
                pass
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 订阅 Redis Pub/Sub
        pubsub = redis_client.pubsub()
        channel = f"ai-backtest-progress:{bt_id}"
        await pubsub.subscribe(channel)

        try:
            start = asyncio.get_event_loop().time()
            timeout = 3600
            while True:
                if asyncio.get_event_loop().time() - start > timeout:
                    break
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=5.0
                )
                if msg is None:
                    continue
                if msg.get("type") == "message":
                    yield f"data: {msg.get('data')}\n\n"
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