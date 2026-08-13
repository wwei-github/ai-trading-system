"""交易记录接口。"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.trade import (
    TradeImportRequest,
    TradeImportResponse,
    TradeQueryParams,
    TradeResponse,
    TradeTagUpdate,
)
from app.services.trade_service import TradeService

router = APIRouter(prefix="/trades", tags=["交易记录"])


@router.get("/health", summary="健康检查")
async def health_check():
    """交易记录模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "trades"})


@router.get("", summary="查询交易记录列表")
async def list_trades(
    exchange: Optional[str] = Query(None, description="交易所筛选"),
    symbol: Optional[str] = Query(None, description="交易对筛选"),
    side: Optional[str] = Query(None, description="方向：buy/sell"),
    status: Optional[str] = Query(None, description="状态筛选"),
    strategy_id: Optional[uuid.UUID] = Query(None, description="关联策略筛选"),
    start_date: Optional[datetime] = Query(None, description="起始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询交易记录列表（分页 + 多条件筛选）。"""
    params = TradeQueryParams(
        exchange=exchange,
        symbol=symbol,
        side=side,
        status=status,
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    service = TradeService(db)
    trades, total = await service.list_trades(current_user.id, params)
    return ApiResponse(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[TradeResponse.model_validate(t) for t in trades],
        )
    )


@router.get("/export", summary="导出交易记录")
async def export_trades(
    exchange: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    side: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    fmt: str = Query("csv", description="导出格式：csv / json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出交易记录（CSV/JSON）。"""
    params = TradeQueryParams(
        exchange=exchange,
        symbol=symbol,
        side=side,
        status=status,
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
        page=1,
        page_size=100,
    )
    service = TradeService(db)
    content = await service.export_trades(current_user.id, params, fmt=fmt)

    if fmt == "json":
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=trades.json"
            },
        )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=trades.csv"
        },
    )


@router.post("/import", summary="批量导入交易记录")
async def import_trades(
    data: TradeImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量导入交易记录。"""
    service = TradeService(db)
    result = await service.import_trades(
        current_user.id, data.account_id, data.trades
    )
    return ApiResponse(data=TradeImportResponse(**result))


@router.get("/{trade_id}", summary="获取交易详情")
async def get_trade(
    trade_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单条交易记录详情。"""
    service = TradeService(db)
    trade = await service.get_trade(trade_id)
    if trade is None:
        raise NotFoundException(
            message="交易记录不存在", detail={"trade_id": str(trade_id)}
        )
    return ApiResponse(data=TradeResponse.model_validate(trade))


@router.patch("/{trade_id}/tags", summary="更新交易标签/备注")
async def update_trade_tags(
    trade_id: uuid.UUID,
    data: TradeTagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新交易记录的标签和备注。"""
    service = TradeService(db)
    trade = await service.update_trade_tags(trade_id, data)
    if trade is None:
        raise NotFoundException(
            message="交易记录不存在", detail={"trade_id": str(trade_id)}
        )
    return ApiResponse(data=TradeResponse.model_validate(trade))
