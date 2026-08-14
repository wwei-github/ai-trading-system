"""交易记录接口。

Stage 3 完整端点：
- GET    /trades                      多维筛选 + 分页查询
- POST   /trades                      手动创建（source=manual）
- GET    /trades/export               流式导出（CSV/JSON）
- POST   /trades/import/preview       导入预览 + 去重检测
- POST   /trades/import/confirm       确认导入
- POST   /trades/recalc               盈亏重算
- GET    /trades/{trade_id}           获取详情
- PATCH  /trades/{trade_id}           更新（来源只读保护）
- DELETE /trades/{trade_id}           删除（exchange_sync 禁删）
- PATCH  /trades/{trade_id}/tags      更新标签/备注
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.core.permissions import reject_viewer_write
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.trade import (
    TradeCreate,
    TradeImportPreviewResponse,
    TradeImportRequest,
    TradeImportResponse,
    TradeQueryParams,
    TradeRecalcRequest,
    TradeRecalcResponse,
    TradeResponse,
    TradeTagUpdate,
    TradeUpdate,
)
from app.services.trade_service import TradeService
from app.utils.audit import write_audit_log

router = APIRouter(
    prefix="/trades",
    tags=["交易记录"],
    dependencies=[Depends(reject_viewer_write)],
)


@router.get("/health", summary="健康检查")
async def health_check():
    """交易记录模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "trades"})


@router.get("", summary="查询交易记录列表")
async def list_trades(
    exchange: Optional[str] = Query(None, description="交易所筛选"),
    symbol: Optional[str] = Query(None, description="交易对筛选"),
    account_id: Optional[uuid.UUID] = Query(None, description="账号筛选"),
    strategy_id: Optional[uuid.UUID] = Query(None, description="策略筛选"),
    side: Optional[str] = Query(None, description="方向：buy/sell"),
    status: Optional[str] = Query(None, description="状态筛选"),
    source: Optional[str] = Query(None, description="来源筛选"),
    pnl_status: Optional[str] = Query(
        None, description="盈亏状态：profit/loss/breakeven/unrealized"
    ),
    search: Optional[str] = Query(None, description="全文搜索（symbol/note）"),
    start_date: Optional[datetime] = Query(None, description="起始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    sort_by: str = Query("executed_at", description="排序字段"),
    sort_order: str = Query("desc", description="asc/desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询交易记录列表（分页 + 多条件筛选 + 标签 + 盈亏状态 + 全文搜索）。"""
    params = TradeQueryParams(
        exchange=exchange,
        symbol=symbol,
        account_id=account_id,
        strategy_id=strategy_id,
        side=side,
        status=status,
        source=source,
        pnl_status=pnl_status,
        search=search,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
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


@router.post("", summary="手动创建交易记录")
async def create_trade(
    data: TradeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动创建交易记录（source 固定为 manual）。"""
    service = TradeService(db)
    trade = await service.create_trade(current_user, data)
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="create",
        resource_type="trade",
        resource_id=trade.id,
        detail={"symbol": trade.symbol, "side": trade.side, "source": "manual"},
    )
    return ApiResponse(data=TradeResponse.model_validate(trade))


@router.get("/export", summary="导出交易记录")
async def export_trades(
    exchange: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    account_id: Optional[uuid.UUID] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    side: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    pnl_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    fmt: str = Query("csv", description="导出格式：csv / json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出交易记录（CSV 流式 / JSON）。"""
    params = TradeQueryParams(
        exchange=exchange,
        symbol=symbol,
        account_id=account_id,
        strategy_id=strategy_id,
        side=side,
        status=status,
        source=source,
        pnl_status=pnl_status,
        search=search,
        start_date=start_date,
        end_date=end_date,
        page=1,
        page_size=100,
    )
    service = TradeService(db)

    if fmt == "json":
        content = await service.export_trades_json(current_user.id, params)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=trades.json"
            },
        )

    # CSV 流式
    async def csv_stream():
        async for chunk in service.export_trades_csv(current_user.id, params):
            yield chunk

    return StreamingResponse(
        csv_stream(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=trades.csv"
        },
    )


@router.post("/import/preview", summary="导入预览 + 去重检测")
async def preview_import(
    data: TradeImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入预览：校验每行 + 去重检测，不写入数据库。"""
    service = TradeService(db)
    result = await service.preview_import(
        current_user.id, data.account_id, data.trades
    )
    return ApiResponse(data=result)


@router.post("/import/confirm", summary="确认导入")
async def confirm_import(
    data: TradeImportRequest,
    skip_duplicates: bool = Query(True, description="是否跳过重复行"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """确认导入（实际写入数据库，source=import）。"""
    service = TradeService(db)
    result = await service.confirm_import(
        current_user.id, data.account_id, data.trades, skip_duplicates
    )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="import",
        resource_type="trade",
        detail={
            "account_id": str(data.account_id),
            "imported": result["imported"],
            "skipped": result["skipped"],
        },
    )
    return ApiResponse(data=TradeImportResponse(**result))


# 兼容旧导入端点
@router.post("/import", summary="批量导入交易记录（直接导入）")
async def import_trades(
    data: TradeImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量导入交易记录（直接导入，跳过预览）。"""
    service = TradeService(db)
    result = await service.confirm_import(
        current_user.id, data.account_id, data.trades, skip_duplicates=True
    )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="import",
        resource_type="trade",
        detail={
            "account_id": str(data.account_id),
            "imported": result["imported"],
        },
    )
    return ApiResponse(data=TradeImportResponse(**result))


@router.post("/recalc", summary="盈亏重算")
async def recalc_pnl(
    data: TradeRecalcRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新计算盈亏（支持指定 trade_ids 或按区间/symbol 重算）。"""
    service = TradeService(db)
    result = await service.recalc_pnl(
        user_id=current_user.id,
        trade_ids=data.trade_ids,
        start_date=data.start_date,
        end_date=data.end_date,
        symbol=data.symbol,
    )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="update",
        resource_type="trade",
        detail={"action": "recalc_pnl", **result},
    )
    return ApiResponse(data=TradeRecalcResponse(**result))


@router.get("/{trade_id}", summary="获取交易详情")
async def get_trade(
    trade_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单条交易记录详情。"""
    service = TradeService(db)
    trade = await service.get_trade(trade_id, current_user.id)
    if trade is None:
        raise NotFoundException(
            message="交易记录不存在", detail={"trade_id": str(trade_id)}
        )
    return ApiResponse(data=TradeResponse.model_validate(trade))


@router.patch("/{trade_id}", summary="更新交易记录")
async def update_trade(
    trade_id: uuid.UUID,
    data: TradeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新交易记录（exchange_sync 来源仅允许更新 tags/note/strategy_id）。"""
    service = TradeService(db)
    trade = await service.update_trade(trade_id, current_user.id, data)
    if trade is None:
        raise NotFoundException(
            message="交易记录不存在", detail={"trade_id": str(trade_id)}
        )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="update",
        resource_type="trade",
        resource_id=trade.id,
        detail=data.model_dump(exclude_unset=True, exclude_none=True),
    )
    return ApiResponse(data=TradeResponse.model_validate(trade))


@router.delete("/{trade_id}", summary="删除交易记录")
async def delete_trade(
    trade_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除交易记录（exchange_sync 来源禁止删除）。"""
    service = TradeService(db)
    deleted = await service.delete_trade(trade_id, current_user.id)
    if not deleted:
        raise NotFoundException(
            message="交易记录不存在", detail={"trade_id": str(trade_id)}
        )
    await write_audit_log(
        db,
        user_id=current_user.id,
        action="delete",
        resource_type="trade",
        resource_id=trade_id,
    )
    return ApiResponse(data={"deleted": True})


@router.patch("/{trade_id}/tags", summary="更新交易标签/备注")
async def update_trade_tags(
    trade_id: uuid.UUID,
    data: TradeTagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新交易记录的标签和备注（所有来源均允许）。"""
    service = TradeService(db)
    trade = await service.update_trade_tags(trade_id, current_user.id, data)
    if trade is None:
        raise NotFoundException(
            message="交易记录不存在", detail={"trade_id": str(trade_id)}
        )
    return ApiResponse(data=TradeResponse.model_validate(trade))
