"""统计分析接口。"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.statistics import StatisticsQueryParams
from app.services.statistics_service import StatisticsService

router = APIRouter(prefix="/statistics", tags=["统计分析"])


def _build_params(
    account_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    symbol: Optional[str] = None,
) -> StatisticsQueryParams:
    """构建统计查询参数。"""
    return StatisticsQueryParams(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        symbol=symbol,
    )


@router.get("/health", summary="健康检查")
async def health_check():
    """统计分析模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "statistics"})


@router.get("/summary", summary="交易汇总指标")
async def get_summary(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取交易汇总指标（总笔数、成交额、手续费、胜率等）。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    summary = await service.get_trade_summary(current_user.id, params)
    return ApiResponse(data=summary)


@router.get("/pnl", summary="盈亏按周期统计")
async def get_pnl(
    period: str = Query("daily", description="周期：daily/weekly/monthly"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """盈亏按周期统计（折线图数据）。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    pnl = await service.get_pnl_by_period(current_user.id, params, period)
    return ApiResponse(data=[p.model_dump() for p in pnl])


@router.get("/coins", summary="币种维度统计")
async def get_coins(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按币种维度统计（柱状图数据）。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    coins = await service.get_coin_stats(current_user.id, params)
    return ApiResponse(data=[c.model_dump() for c in coins])


@router.get("/asset-trend", summary="资产趋势")
async def get_asset_trend(
    account_id: Optional[str] = Query(None, description="按账号筛选"),
    days: int = Query(30, ge=1, le=365, description="天数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """资产趋势（面积图数据）。"""
    service = StatisticsService(db)
    trend = await service.get_asset_trend(
        current_user.id, account_id=account_id, days=days
    )
    return ApiResponse(data=[t.model_dump() for t in trend])


@router.get("/exchange-distribution", summary="交易所分布")
async def get_exchange_distribution(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按交易所分布统计（饼图数据）。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    data = await service.get_exchange_distribution(current_user.id, params)
    return ApiResponse(data=data)


@router.get("/side-distribution", summary="买卖方向分布")
async def get_side_distribution(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按买卖方向分布统计。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    data = await service.get_side_distribution(current_user.id, params)
    return ApiResponse(data=data)


@router.get("/time-distribution", summary="交易时间分布")
async def get_time_distribution(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按交易时间（小时）分布统计。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    data = await service.get_time_distribution(current_user.id, params)
    return ApiResponse(data=data)


@router.get("/strategy-comparison", summary="策略收益对比")
async def get_strategy_comparison(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """策略收益对比。"""
    service = StatisticsService(db)
    data = await service.get_strategy_comparison(current_user.id)
    return ApiResponse(data=data)


@router.get("/monthly-report", summary="月度报表")
async def get_monthly_report(
    year: Optional[int] = Query(None, description="年份，默认当前年"),
    month: Optional[int] = Query(None, ge=1, le=12, description="月份，默认当前月"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取月度报表。"""
    service = StatisticsService(db)
    data = await service.get_monthly_report(
        current_user.id, year=year, month=month
    )
    return ApiResponse(data=data)


@router.get("/export", summary="报表导出")
async def export_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出统计报表为 CSV。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    content = await service.export_report(current_user.id, params)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=statistics_report.csv"
        },
    )
