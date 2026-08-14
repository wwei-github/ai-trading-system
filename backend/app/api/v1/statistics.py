"""统计分析接口。

Stage 4 完整端点（基于 Trade.pnl 真实盈亏）：
- GET /statistics/health                     健康检查
- GET /statistics/metrics                    14 项核心指标（5 维过滤 + 时间预设）
- GET /statistics/equity-curve               权益曲线
- GET /statistics/monthly-pnl                月度盈亏柱状图
- GET /statistics/pnl-distribution           盈亏分布直方图
- GET /statistics/symbol-contribution        币种贡献度饼图
- GET /statistics/strategy-contribution      策略贡献度柱状图
- GET /statistics/heatmap                    星期×小时热力图
- GET /statistics/asset-composition          资产构成饼图（最近快照）
- GET /statistics/drawdown-curve             回撤曲线
- GET /statistics/pnl-scatter                每笔盈亏散点
- GET /statistics/report                     报表 5 章（结构化 JSON）
- GET /statistics/team-overview              团队视角（Admin）
- GET /statistics/export                     CSV 导出（兼容）

兼容旧端点（保留）：
- GET /statistics/summary
- GET /statistics/pnl
- GET /statistics/coins
- GET /statistics/asset-trend
- GET /statistics/exchange-distribution
- GET /statistics/side-distribution
- GET /statistics/time-distribution
- GET /statistics/strategy-comparison
- GET /statistics/monthly-report
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.permissions import require_roles
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.statistics import StatisticsQueryParams
from app.services.statistics_service import (
    STATS_CACHE_PREFIX,
    STATS_CACHE_TTL,
    StatisticsService,
)

router = APIRouter(prefix="/statistics", tags=["统计分析"])


def _build_params(
    account_id: Optional[str] = None,
    strategy_id: Optional[uuid.UUID] = None,
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    tags: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period_preset: Optional[str] = None,
) -> StatisticsQueryParams:
    """构建统计查询参数（5 维过滤 + 时间）。"""
    return StatisticsQueryParams(
        account_id=uuid.UUID(account_id) if account_id else None,
        strategy_id=strategy_id,
        symbol=symbol,
        side=side,
        tags=tags,
        start_date=start_date,
        end_date=end_date,
        period_preset=period_preset,
    )


@router.get("/health", summary="健康检查")
async def health_check():
    """统计分析模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "statistics"})


# ==================== Stage 4 新端点 ====================


@router.get("/metrics", summary="14 项核心指标")
async def get_core_metrics(
    account_id: Optional[str] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    symbol: Optional[str] = Query(None),
    side: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None, description="标签数组"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(
        None,
        description="快捷预设：today/week/month/quarter/year/all",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 14 项核心指标（PRD §5.4.1）。

    指标清单：PnL 总盈亏 / 总收益率 / 交易次数 / 胜率 / 平均盈亏比 /
    最大回撤 / 夏普 / Sortino / 平均持仓时长 / 盈利笔数 / 亏损笔数 /
    最大单笔盈 / 最大单笔亏 / 总手续费。
    """
    params = _build_params(
        account_id=account_id,
        strategy_id=strategy_id,
        symbol=symbol,
        side=side,
        tags=tags,
        start_date=start_date,
        end_date=end_date,
        period_preset=period_preset,
    )
    service = StatisticsService(db)
    metrics = await service.get_core_metrics(current_user.id, params)
    return ApiResponse(data=metrics.model_dump(mode="json"))


@router.get("/equity-curve", summary="权益曲线")
async def get_equity_curve(
    account_id: Optional[str] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    symbol: Optional[str] = Query(None),
    side: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """权益曲线（按日累计 pnl，折线图数据）。"""
    params = _build_params(
        account_id=account_id, strategy_id=strategy_id, symbol=symbol,
        side=side, start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    data = await service.get_equity_curve(current_user.id, params)
    return ApiResponse(data=[d.model_dump(mode="json") for d in data])


@router.get("/monthly-pnl", summary="月度盈亏柱状图")
async def get_monthly_pnl(
    account_id: Optional[str] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    symbol: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """月度盈亏柱状图（按月聚合 pnl）。"""
    params = _build_params(
        account_id=account_id, strategy_id=strategy_id, symbol=symbol,
        start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    data = await service.get_monthly_pnl(current_user.id, params)
    return ApiResponse(data=[d.model_dump(mode="json") for d in data])


@router.get("/pnl-distribution", summary="盈亏分布直方图")
async def get_pnl_distribution(
    account_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    bin_count: int = Query(10, ge=5, le=50, description="分桶数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """盈亏分布直方图（Postgres width_bucket 分桶）。"""
    params = _build_params(
        account_id=account_id, symbol=symbol,
        start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    data = await service.get_pnl_distribution(current_user.id, params, bin_count)
    return ApiResponse(data=[d.model_dump(mode="json") for d in data])


@router.get("/symbol-contribution", summary="币种贡献度饼图")
async def get_symbol_contribution(
    account_id: Optional[str] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    symbol: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """币种贡献度饼图（按 symbol GROUP BY pnl）。"""
    params = _build_params(
        account_id=account_id, strategy_id=strategy_id, symbol=symbol,
        start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    data = await service.get_symbol_contribution(current_user.id, params)
    return ApiResponse(data=[d.model_dump(mode="json") for d in data])


@router.get("/strategy-contribution", summary="策略贡献度柱状图")
async def get_strategy_contribution(
    account_id: Optional[str] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """策略贡献度柱状图（含策略名 JOIN）。"""
    params = _build_params(
        account_id=account_id, strategy_id=strategy_id,
        start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    data = await service.get_strategy_contribution(current_user.id, params)
    return ApiResponse(data=[d.model_dump(mode="json") for d in data])


@router.get("/heatmap", summary="星期×小时热力图")
async def get_heatmap(
    account_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """星期（0=周一）× 小时（0-23）热力图。"""
    params = _build_params(
        account_id=account_id, symbol=symbol,
        start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    data = await service.get_heatmap(current_user.id, params)
    return ApiResponse(data=[d.model_dump(mode="json") for d in data])


@router.get("/asset-composition", summary="资产构成饼图（最近快照）")
async def get_asset_composition(
    account_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """资产构成饼图（基于最近一次资产快照，按币种聚合）。"""
    service = StatisticsService(db)
    data = await service.get_asset_composition(
        current_user.id,
        account_id=uuid.UUID(account_id) if account_id else None,
    )
    return ApiResponse(data=[d.model_dump(mode="json") for d in data])


@router.get("/drawdown-curve", summary="回撤曲线")
async def get_drawdown_curve(
    account_id: Optional[str] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    symbol: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """回撤曲线（基于权益 - 滚动 peak）。"""
    params = _build_params(
        account_id=account_id, strategy_id=strategy_id, symbol=symbol,
        start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    data = await service.get_drawdown_curve(current_user.id, params)
    return ApiResponse(data=[d.model_dump(mode="json") for d in data])


@router.get("/pnl-scatter", summary="每笔盈亏散点")
async def get_pnl_scatter(
    account_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """每笔盈亏散点（pnl vs holding_seconds；上限 500 点）。"""
    params = _build_params(
        account_id=account_id, symbol=symbol,
        start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    data = await service.get_pnl_scatter(current_user.id, params)
    return ApiResponse(data=[d.model_dump(mode="json") for d in data])


@router.get("/report", summary="统计报表（5 章结构化 JSON）")
async def get_report(
    account_id: Optional[str] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    symbol: Optional[str] = Query(None),
    side: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    title: Optional[str] = Query(None, description="报表标题"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成 5 章统计报表（封面 / 指标 / 图表 / Top10 / AI 占位）。

    PDF / Excel 导出可在此接口数据基础上前端二次加工或调用 /export CSV。
    """
    params = _build_params(
        account_id=account_id, strategy_id=strategy_id, symbol=symbol, side=side,
        start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    report = await service.get_report(current_user.id, params, title=title)
    return ApiResponse(data=report.model_dump(mode="json"))


@router.get(
    "/team-overview",
    summary="团队视角聚合（Admin）",
    dependencies=[Depends(require_roles("admin"))],
)
async def get_team_overview(
    symbol: Optional[str] = Query(None),
    strategy_id: Optional[uuid.UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_preset: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin 团队整体报表（按 user_id GROUP BY）。"""
    params = _build_params(
        strategy_id=strategy_id, symbol=symbol,
        start_date=start_date, end_date=end_date, period_preset=period_preset,
    )
    service = StatisticsService(db)
    data = await service.get_team_overview(params)
    return ApiResponse(data=data.model_dump(mode="json"))


# ==================== 兼容旧端点（保留向后兼容） ====================


@router.get("/summary", summary="[兼容] 交易汇总指标")
async def get_summary(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 交易汇总指标。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    summary = await service.get_trade_summary(current_user.id, params)
    return ApiResponse(data=summary.model_dump(mode="json"))


@router.get("/pnl", summary="[兼容] 盈亏按周期统计")
async def get_pnl(
    period: str = Query("daily", description="daily/weekly/monthly"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 盈亏按周期统计（折线图数据）。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    pnl = await service.get_pnl_by_period(current_user.id, params, period)
    return ApiResponse(data=[p.model_dump(mode="json") for p in pnl])


@router.get("/coins", summary="[兼容] 币种维度统计")
async def get_coins(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 按币种维度统计。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    coins = await service.get_coin_stats(current_user.id, params)
    return ApiResponse(data=[c.model_dump(mode="json") for c in coins])


@router.get("/asset-trend", summary="[兼容] 资产趋势")
async def get_asset_trend(
    account_id: Optional[str] = Query(None, description="按账号筛选"),
    days: int = Query(30, ge=1, le=365, description="天数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 资产趋势（面积图数据）。"""
    service = StatisticsService(db)
    trend = await service.get_asset_trend(
        current_user.id, account_id=account_id, days=days
    )
    return ApiResponse(data=[t.model_dump(mode="json") for t in trend])


@router.get("/exchange-distribution", summary="[兼容] 交易所分布")
async def get_exchange_distribution(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 按交易所分布统计。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    data = await service.get_exchange_distribution(current_user.id, params)
    return ApiResponse(data=data)


@router.get("/side-distribution", summary="[兼容] 买卖方向分布")
async def get_side_distribution(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 按买卖方向分布统计。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    data = await service.get_side_distribution(current_user.id, params)
    return ApiResponse(data=data)


@router.get("/time-distribution", summary="[兼容] 交易时间分布")
async def get_time_distribution(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 按交易时间（小时）分布统计。"""
    params = _build_params(start_date=start_date, end_date=end_date, symbol=symbol)
    service = StatisticsService(db)
    data = await service.get_time_distribution(current_user.id, params)
    return ApiResponse(data=data)


@router.get("/strategy-comparison", summary="[兼容] 策略收益对比")
async def get_strategy_comparison(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 策略收益对比。"""
    service = StatisticsService(db)
    data = await service.get_strategy_comparison(current_user.id)
    return ApiResponse(data=data)


@router.get("/monthly-report", summary="[兼容] 月度报表")
async def get_monthly_report(
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, ge=1, le=12, description="月份"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 获取月度报表。"""
    service = StatisticsService(db)
    data = await service.get_monthly_report(
        current_user.id, year=year, month=month
    )
    return ApiResponse(data=data)


@router.get("/export", summary="[兼容] 报表导出 CSV")
async def export_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    symbol: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 导出统计报表为 CSV。"""
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
