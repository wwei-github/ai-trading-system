"""策略接口。"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.core.permissions import reject_viewer_write
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.strategy import (
    BacktestCreate,
    BacktestResponse,
    LiveTradeRequest,
    PaperTradeRequest,
    StrategyCreate,
    StrategyResponse,
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


@router.get("", summary="获取策略列表")
async def list_strategies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的全部策略。"""
    service = StrategyService(db)
    strategies = await service.list_strategies(current_user.id)
    return ApiResponse(
        data=[StrategyResponse.model_validate(s) for s in strategies]
    )


@router.post("", summary="创建策略", status_code=201)
async def create_strategy(
    data: StrategyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建策略。"""
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
    """更新策略信息。"""
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
    """删除策略。"""
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


# ---------- 回测 ----------


@router.post("/{strategy_id}/backtest", summary="触发策略回测", status_code=201)
async def create_backtest(
    strategy_id: uuid.UUID,
    data: BacktestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发策略回测（异步任务）。"""
    service = StrategyService(db)
    # 强制使用路径中的 strategy_id
    data.strategy_id = strategy_id
    backtest = await service.create_backtest(current_user.id, data)
    return ApiResponse(data=BacktestResponse.model_validate(backtest))


@router.get("/{strategy_id}/backtests", summary="获取回测历史")
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


@router.post("/{strategy_id}/paper-trade", summary="模拟交易")
async def paper_trade(
    strategy_id: uuid.UUID,
    data: PaperTradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """模拟交易（不实际下单）。"""
    service = StrategyService(db)
    result = await service.paper_trade(current_user.id, strategy_id, data)
    return ApiResponse(data=result)


@router.post("/{strategy_id}/live-trade", summary="实盘交易")
async def live_trade(
    strategy_id: uuid.UUID,
    data: LiveTradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """实盘交易（需二次确认）。"""
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
