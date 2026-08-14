"""策略接口（Stage 6 完整实现）。

路由顺序：顶层路径（/backtests/... /paper-trading/... /live-trading/...）
必须声明在 /{strategy_id} 之前，避免路径参数冲突。
"""

import asyncio
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.database import redis_client
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.permissions import reject_viewer_write
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.strategy import (
    BacktestCompareRequest,
    BacktestCreate,
    BacktestResponse,
    BacktestTradeResponse,
    LiveOrderResponse,
    LiveTradeRequest,
    LiveTradingStartRequest,
    LiveTradingStopRequest,
    PaperAccountResponse,
    PaperTradeRequest,
    PaperTradeResponse,
    PaperTradingControlRequest,
    PaperTradingStartRequest,
    StrategyCloneRequest,
    StrategyCreate,
    StrategyDetailResponse,
    StrategyResponse,
    StrategyRulesUpdate,
    StrategyUpdate,
)
from app.services.strategy_service import StrategyService
from app.utils.audit import write_audit_log

router = APIRouter(
    prefix="/strategies",
    tags=["策略管理"],
    dependencies=[Depends(reject_viewer_write)],
)


@router.get("/health", summary="健康检查")
async def health_check():
    """策略模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "strategies"})


# =====================================================================
# 回测管理（顶层路径，必须在 /{strategy_id} 之前声明）
# =====================================================================


@router.post("/backtests/compare", summary="对比两次回测")
async def compare_backtests(
    data: BacktestCompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对比两次回测结果（PRD §5.6.3 R2）。

    返回指标差异 + 合并权益曲线。
    """
    service = StrategyService(db)
    result = await service.compare_backtests(data.backtest_id_a, data.backtest_id_b)
    return ApiResponse(data=result)


@router.get("/backtests/{backtest_id}", summary="获取回测详情")
async def get_backtest(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取回测详情（含结果指标、权益曲线、回撤曲线）。"""
    service = StrategyService(db)
    backtest = await service.get_backtest(backtest_id)
    if backtest is None:
        raise NotFoundException(
            message="回测不存在", detail={"backtest_id": str(backtest_id)}
        )
    return ApiResponse(data=BacktestResponse.model_validate(backtest))


@router.get(
    "/backtests/{backtest_id}/trades",
    summary="获取回测交易明细",
)
async def get_backtest_trades(
    backtest_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取回测开平仓交易明细。"""
    service = StrategyService(db)
    trades = await service.get_backtest_trades(backtest_id, limit=limit, offset=offset)
    return ApiResponse(
        data=[BacktestTradeResponse.model_validate(t) for t in trades]
    )


@router.get("/backtests/{backtest_id}/progress", summary="回测进度 SSE")
async def backtest_progress_sse(
    backtest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE 流式推送回测进度（PRD §5.6.3 R1）。

    事件格式：`data: {"backtest_id": "...", "stage": "running", "progress": 50, "message": "..."}\\n\\n`
    结束标记：`data: [DONE]\\n\\n`

    stage 取值：init / fetching / running / saving / done / error
    """
    bt_id = str(backtest_id)
    channel = f"backtest:progress:{bt_id}"

    async def event_generator():
        # 1. 检查 DB 当前状态
        service = StrategyService(db)
        backtest = await service.get_backtest(backtest_id)
        if backtest is None:
            yield f"data: {json.dumps({'error': '回测不存在'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 2. 若已完成/失败，直接推送最终状态
        if backtest.status in ("completed", "failed"):
            payload = {
                "backtest_id": bt_id,
                "stage": "done" if backtest.status == "completed" else "error",
                "progress": 100,
                "status": backtest.status,
                "message": "回测已完成" if backtest.status == "completed" else "回测失败",
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 3. 订阅 Redis 频道
        if redis_client is None:
            yield f"data: {json.dumps({'error': 'Redis 不可用，无法订阅进度'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            # 推送连接建立事件
            yield f"data: {json.dumps({'backtest_id': bt_id, 'stage': 'connected', 'progress': 0, 'message': 'SSE 连接已建立'}, ensure_ascii=False)}\n\n"

            timeout_seconds = 600  # 10 分钟超时
            start = asyncio.get_event_loop().time()
            keepalive_counter = 0

            while True:
                if asyncio.get_event_loop().time() - start > timeout_seconds:
                    yield f"data: {json.dumps({'error': '订阅超时（10 分钟）'}, ensure_ascii=False)}\n\n"
                    break

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=5.0
                )
                if msg is None:
                    # 每 15 秒发一次 keepalive（3 次 5 秒 timeout）
                    keepalive_counter += 1
                    if keepalive_counter >= 3:
                        yield ": keepalive\n\n"
                        keepalive_counter = 0
                    continue

                if msg.get("type") == "message":
                    data = msg.get("data")
                    yield f"data: {data}\n\n"
                    # 检查是否结束
                    try:
                        payload = json.loads(data)
                        if payload.get("stage") in ("done", "error"):
                            break
                    except Exception:
                        pass
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception as e:
                logger.warning("关闭 pubsub 失败 | {}", e)

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# =====================================================================
# 模拟交易（顶层路径）
# =====================================================================


@router.post("/paper-trading", summary="启动模拟交易", status_code=201)
async def start_paper_trading(
    data: PaperTradingStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启动模拟交易（PRD §5.6.4 R1）。

    每策略+每币种一个虚拟账号，使用实时行情驱动策略信号。
    """
    service = StrategyService(db)
    account = await service.start_paper_trading(
        user_id=current_user.id,
        strategy_id=data.strategy_id,
        symbol=data.symbol,
        timeframe=data.timeframe,
        initial_capital=data.initial_capital,
    )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="start_paper_trading",
        resource_type="strategy",
        resource_id=data.strategy_id,
        detail={
            "paper_account_id": str(account.id),
            "symbol": data.symbol,
            "initial_capital": data.initial_capital,
        },
    )
    return ApiResponse(data=PaperAccountResponse.model_validate(account))


@router.get("/paper-trading", summary="获取模拟交易列表")
async def list_paper_accounts(
    status: Optional[str] = Query(None, description="状态过滤：running/paused/stopped"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的模拟交易账号列表。"""
    service = StrategyService(db)
    accounts = await service.list_paper_accounts(current_user.id, status=status)
    return ApiResponse(
        data=[PaperAccountResponse.model_validate(a) for a in accounts]
    )


@router.get("/paper-trading/{paper_account_id}", summary="获取模拟交易详情")
async def get_paper_account(
    paper_account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模拟交易账号详情。"""
    service = StrategyService(db)
    account = await service.get_paper_account(paper_account_id)
    if account is None:
        raise NotFoundException(
            message="模拟交易不存在",
            detail={"paper_account_id": str(paper_account_id)},
        )
    return ApiResponse(data=PaperAccountResponse.model_validate(account))


@router.post(
    "/paper-trading/{paper_account_id}/control",
    summary="控制模拟交易（暂停/恢复/终止）",
)
async def control_paper_trading(
    paper_account_id: uuid.UUID,
    data: PaperTradingControlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """控制模拟交易状态（PRD §5.6.4 R2）。

    action: pause（暂停）/ resume（恢复）/ stop（终止）
    """
    service = StrategyService(db)
    account = await service.control_paper_trading(paper_account_id, data.action)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action=f"paper_trading_{data.action}",
        resource_type="paper_account",
        resource_id=paper_account_id,
    )
    return ApiResponse(data=PaperAccountResponse.model_validate(account))


@router.get(
    "/paper-trading/{paper_account_id}/trades",
    summary="获取模拟交易记录",
)
async def list_paper_trades(
    paper_account_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模拟交易的成交记录。"""
    service = StrategyService(db)
    trades = await service.list_paper_trades(
        paper_account_id, limit=limit, offset=offset
    )
    return ApiResponse(
        data=[PaperTradeResponse.model_validate(t) for t in trades]
    )


@router.get(
    "/paper-trading/{paper_account_id}/stream",
    summary="模拟交易实时更新 SSE",
)
async def paper_trading_stream(
    paper_account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """SSE 流式推送模拟交易实时更新（PRD §5.6.4 R3）。

    事件类型：
    - tick：行情快照（价格、权益、持仓、未实现盈亏）
    - trade：虚拟成交（side、price、quantity、realized_pnl）

    由 Celery Beat 每 2 分钟驱动信号生成，成交后推送。
    """
    pa_id = str(paper_account_id)
    channel = f"paper_trading:update:{pa_id}"

    async def event_generator():
        if redis_client is None:
            yield f"data: {json.dumps({'error': 'Redis 不可用'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            yield f"data: {json.dumps({'type': 'connected', 'paper_account_id': pa_id}, ensure_ascii=False)}\n\n"

            timeout_seconds = 3600  # 1 小时超时
            start = asyncio.get_event_loop().time()
            keepalive_counter = 0

            while True:
                if asyncio.get_event_loop().time() - start > timeout_seconds:
                    break

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=5.0
                )
                if msg is None:
                    keepalive_counter += 1
                    if keepalive_counter >= 3:
                        yield ": keepalive\n\n"
                        keepalive_counter = 0
                    continue

                if msg.get("type") == "message":
                    yield f"data: {msg.get('data')}\n\n"
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception as e:
                logger.warning("关闭 pubsub 失败 | {}", e)

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# =====================================================================
# 实盘交易（顶层路径）
# =====================================================================


@router.post("/live-trading", summary="启动实盘策略实例", status_code=201)
async def start_live_trading(
    data: LiveTradingStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启动实盘策略实例（PRD §5.6.5 R6，V1 默认半自动）。"""
    service = StrategyService(db)
    instance = await service.start_live_trading(
        user_id=current_user.id,
        strategy_id=data.strategy_id,
        account_id=data.account_id,
        symbol=data.symbol,
        timeframe=data.timeframe,
        mode=data.mode,
        risk_params=data.risk_params,
    )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="start_live_trading",
        resource_type="strategy",
        resource_id=data.strategy_id,
        detail={
            "instance_id": str(instance.id),
            "account_id": str(data.account_id),
            "symbol": data.symbol,
            "mode": data.mode,
        },
    )
    return ApiResponse(data=instance)


@router.get("/live-trading", summary="获取实盘策略实例列表")
async def list_live_instances(
    status: Optional[str] = Query(None, description="状态过滤：running/paused/stopped"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的实盘策略实例列表。"""
    service = StrategyService(db)
    instances = await service.list_live_instances(current_user.id, status=status)
    return ApiResponse(data=instances)


@router.get("/live-trading/orders", summary="获取实盘信号订单列表")
async def list_live_orders(
    instance_id: Optional[uuid.UUID] = Query(None, description="按实例过滤"),
    status: Optional[str] = Query(None, description="状态过滤：pending/confirmed/executed/rejected/expired"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取实盘信号订单列表（半自动模式待确认的订单）。"""
    service = StrategyService(db)
    orders = await service.list_live_orders(
        current_user.id,
        instance_id=instance_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(data=[LiveOrderResponse.model_validate(o) for o in orders])


@router.get("/live-trading/{instance_id}", summary="获取实盘策略实例详情")
async def get_live_instance(
    instance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取实盘策略实例详情。"""
    service = StrategyService(db)
    instance = await service.get_live_instance(instance_id)
    if instance is None:
        raise NotFoundException(
            message="实盘策略实例不存在",
            detail={"instance_id": str(instance_id)},
        )
    return ApiResponse(data=instance)


@router.post("/live-trading/{instance_id}/pause", summary="暂停实盘策略")
async def pause_live_trading(
    instance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """暂停实盘策略（仅停止生成新信号，不平仓）。"""
    service = StrategyService(db)
    instance = await service.pause_live_trading(instance_id)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="pause_live_trading",
        resource_type="live_instance",
        resource_id=instance_id,
    )
    return ApiResponse(data=instance)


@router.post("/live-trading/{instance_id}/resume", summary="恢复实盘策略")
async def resume_live_trading(
    instance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复已暂停的实盘策略。"""
    service = StrategyService(db)
    instance = await service.resume_live_trading(instance_id)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="resume_live_trading",
        resource_type="live_instance",
        resource_id=instance_id,
    )
    return ApiResponse(data=instance)


@router.post("/live-trading/{instance_id}/stop", summary="停止实盘策略")
async def stop_live_trading(
    instance_id: uuid.UUID,
    data: LiveTradingStopRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """停止实盘策略（PRD §5.6.5 R5）。

    close_positions: True=停止并平所有仓；False=仅停止下单
    """
    service = StrategyService(db)
    instance = await service.stop_live_trading(
        instance_id,
        close_positions=data.close_positions,
        reason=data.reason or "",
    )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="stop_live_trading",
        resource_type="live_instance",
        resource_id=instance_id,
        detail={
            "close_positions": data.close_positions,
            "reason": data.reason,
        },
    )
    return ApiResponse(data=instance)


@router.post(
    "/live-trading/orders/{order_id}/confirm",
    summary="确认实盘信号订单",
)
@rate_limit(settings.RATE_LIMIT_TRADE_PER_MIN)
async def confirm_live_order(
    order_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户确认实盘信号订单（半自动模式，PRD §5.6.5 R6）。

    60s 未确认自动过期。确认后执行风控校验（8 阈值），
    通过则调用交易所下单。
    """
    service = StrategyService(db)
    result = await service.confirm_live_order(order_id, current_user.id)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="confirm_live_order",
        resource_type="live_order",
        resource_id=order_id,
        detail=result,
    )
    return ApiResponse(data=result)


@router.post(
    "/live-trading/orders/{order_id}/reject",
    summary="拒绝实盘信号订单",
)
async def reject_live_order(
    order_id: uuid.UUID,
    payload: dict = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户拒绝实盘信号订单（半自动模式）。"""
    reason = (payload or {}).get("reason", "") if isinstance(payload, dict) else ""
    service = StrategyService(db)
    order = await service.reject_live_order(order_id, current_user.id, reason=reason)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="reject_live_order",
        resource_type="live_order",
        resource_id=order_id,
        detail={"reason": reason},
    )
    return ApiResponse(data=LiveOrderResponse.model_validate(order))


@router.get(
    "/live-trading/{instance_id}/stream",
    summary="实盘信号实时推送 SSE",
)
async def live_trading_stream(
    instance_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
):
    """SSE 流式推送实盘信号（PRD §5.6.5 R6）。

    事件类型：
    - signal：新信号生成（order_id、side、suggested_price、expires_at）
    - 等待用户确认（60s 超时自动过期）

    由 Celery Beat 每 2 分钟驱动信号生成。
    """
    inst_id = str(instance_id)
    channel = f"live_trading:signal:{inst_id}"

    async def event_generator():
        if redis_client is None:
            yield f"data: {json.dumps({'error': 'Redis 不可用'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            yield f"data: {json.dumps({'type': 'connected', 'instance_id': inst_id}, ensure_ascii=False)}\n\n"

            timeout_seconds = 3600
            start = asyncio.get_event_loop().time()
            keepalive_counter = 0

            while True:
                if asyncio.get_event_loop().time() - start > timeout_seconds:
                    break

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=5.0
                )
                if msg is None:
                    keepalive_counter += 1
                    if keepalive_counter >= 3:
                        yield ": keepalive\n\n"
                        keepalive_counter = 0
                    continue

                if msg.get("type") == "message":
                    yield f"data: {msg.get('data')}\n\n"
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception as e:
                logger.warning("关闭 pubsub 失败 | {}", e)

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# =====================================================================
# 策略 CRUD（含 /{strategy_id} 路径）
# =====================================================================


@router.get("", summary="获取策略列表")
async def list_strategies(
    include_templates: bool = Query(True, description="是否包含内置模板"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的全部策略（含内置模板）。"""
    service = StrategyService(db)
    strategies = await service.list_strategies(
        current_user.id, include_templates=include_templates
    )
    return ApiResponse(
        data=[StrategyResponse.model_validate(s) for s in strategies]
    )


@router.post("", summary="创建策略", status_code=201)
async def create_strategy(
    data: StrategyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建策略（含 DSL 校验）。"""
    service = StrategyService(db)
    strategy = await service.create_strategy(current_user.id, data)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="create",
        resource_type="strategy",
        resource_id=strategy.id,
        detail={"name": strategy.name, "category": strategy.category},
    )
    return ApiResponse(data=StrategyResponse.model_validate(strategy))


@router.get("/{strategy_id}", summary="获取策略详情")
async def get_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取策略详情。"""
    service = StrategyService(db)
    strategy = await service.get_strategy(strategy_id)
    if strategy is None:
        raise NotFoundException(
            message="策略不存在", detail={"strategy_id": str(strategy_id)}
        )
    return ApiResponse(data=StrategyResponse.model_validate(strategy))


@router.patch("/{strategy_id}", summary="更新策略")
async def update_strategy(
    strategy_id: uuid.UUID,
    data: StrategyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新策略信息（模板策略不可编辑）。"""
    service = StrategyService(db)
    strategy = await service.update_strategy(strategy_id, data)
    if strategy is None:
        raise NotFoundException(
            message="策略不存在", detail={"strategy_id": str(strategy_id)}
        )
    return ApiResponse(data=StrategyResponse.model_validate(strategy))


@router.delete("/{strategy_id}", summary="删除策略")
async def delete_strategy(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除策略（模板策略不可删）。"""
    service = StrategyService(db)
    deleted = await service.delete_strategy(strategy_id)
    if not deleted:
        raise NotFoundException(
            message="策略不存在", detail={"strategy_id": str(strategy_id)}
        )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="delete",
        resource_type="strategy",
        resource_id=strategy_id,
    )
    return ApiResponse(data={"deleted": True})


@router.post("/{strategy_id}/clone", summary="克隆策略", status_code=201)
async def clone_strategy(
    strategy_id: uuid.UUID,
    data: StrategyCloneRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """克隆策略（PRD §5.6.1 R2，模板策略克隆后可编辑）。"""
    new_name = data.new_name if data else None
    service = StrategyService(db)
    cloned = await service.clone_strategy(strategy_id, current_user.id, new_name)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="clone",
        resource_type="strategy",
        resource_id=cloned.id,
        detail={"source_id": str(strategy_id), "new_name": cloned.name},
    )
    return ApiResponse(data=StrategyResponse.model_validate(cloned))


@router.patch("/{strategy_id}/rules", summary="更新策略规则")
async def update_strategy_rules(
    strategy_id: uuid.UUID,
    data: StrategyRulesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """结构化更新策略规则（仅更新入场/出场/仓位/风控等独立字段）。

    请求体示例：
    ```json
    {
      "entry_rules": [
        {
          "logic": "AND",
          "conditions": [
            {
              "indicator": "MA5",
              "operator": "cross_above",
              "value": "MA20",
              "description": "金叉买入"
            }
          ]
        }
      ],
      "exit_rules": [...],
      "position_sizing": {...},
      "risk_control": {...}
    }
    ```
    """
    service = StrategyService(db)
    strategy = await service.update_strategy_rules(strategy_id, data)
    if strategy is None:
        raise NotFoundException(
            message="策略不存在",
            detail={"strategy_id": str(strategy_id)},
        )
    return ApiResponse(data=StrategyDetailResponse.model_validate(strategy))


@router.get("/{strategy_id}/detail", summary="获取策略完整详情")
async def get_strategy_detail(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取策略完整详情（含结构化规则字段）。"""
    service = StrategyService(db)
    strategy = await service.get_strategy_detail(strategy_id)
    if strategy is None:
        raise NotFoundException(
            message="策略不存在",
            detail={"strategy_id": str(strategy_id)},
        )
    return ApiResponse(data=StrategyDetailResponse.model_validate(strategy))


# =====================================================================
# 策略级回测（兼容接口，保留原路径）
# =====================================================================


@router.post("/{strategy_id}/backtest", summary="触发策略回测", status_code=201)
async def create_backtest(
    strategy_id: uuid.UUID,
    data: BacktestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发策略回测（异步任务，通过 SSE 订阅进度）。"""
    service = StrategyService(db)
    # 强制使用路径中的 strategy_id
    data.strategy_id = strategy_id
    backtest = await service.create_backtest(current_user.id, data)
    return ApiResponse(data=BacktestResponse.model_validate(backtest))


@router.get("/{strategy_id}/backtests", summary="获取策略回测历史")
async def list_backtests(
    strategy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取策略的回测历史。"""
    service = StrategyService(db)
    backtests = await service.list_backtests(strategy_id)
    return ApiResponse(
        data=[BacktestResponse.model_validate(b) for b in backtests]
    )


# =====================================================================
# 兼容接口（手动单笔交易）
# =====================================================================


@router.post("/{strategy_id}/paper-trade", summary="[兼容] 手动模拟交易")
async def paper_trade(
    strategy_id: uuid.UUID,
    data: PaperTradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 手动模拟交易（单笔，不实际下单）。"""
    service = StrategyService(db)
    result = await service.paper_trade(current_user.id, strategy_id, data)
    return ApiResponse(data=result)


@router.post("/{strategy_id}/live-trade", summary="[兼容] 实盘交易")
async def live_trade(
    strategy_id: uuid.UUID,
    data: LiveTradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 直接实盘下单（需二次确认）。"""
    service = StrategyService(db)
    result = await service.live_trade(current_user.id, strategy_id, data)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="live_trade",
        resource_type="strategy",
        resource_id=strategy_id,
        detail={
            "symbol": data.symbol,
            "side": data.side,
            "amount": data.amount,
            "account_id": str(data.account_id),
        },
    )
    return ApiResponse(data=result)
