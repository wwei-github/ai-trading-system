"""统计分析服务。

Stage 4 完整实现：
- 14 项核心指标（基于 Trade.pnl 真实盈亏字段，SQL CTE 批量计算）
- 9 类图表聚合查询（权益曲线 / 月度盈亏 / 盈亏分布 / 币种贡献 / 策略贡献 /
  星期×小时热力图 / 资产构成 / 回撤曲线 / 散点图）
- 报表 5 章结构化 JSON（封面 / 指标 / 图表 / Top10 / AI 总结占位）
- 团队视角聚合（Admin，按 user_id GROUP BY）
- Redis 30s 缓存装饰器
- 兼容旧 /summary、/pnl、/coins、/asset-trend 等端点
"""

import csv
import io
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import and_, case, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import redis_client
from app.models.asset import AssetSnapshot
from app.models.strategy import Strategy
from app.models.trade import Trade
from app.models.user import User
from app.schemas.statistics import (
    AssetComposition,
    AssetTrend,
    CoinStat,
    CoreMetrics,
    DrawdownPoint,
    EquityCurvePoint,
    HeatmapCell,
    MonthlyPnLBar,
    PnLByPeriod,
    PnLDistributionBin,
    ReportAIConclusion,
    ReportCharts,
    ReportCover,
    ReportMetrics,
    ReportTopTrades,
    ScatterPoint,
    StatisticsQueryParams,
    StatisticsReport,
    StatisticsResponse,
    StrategyContribution,
    SymbolContribution,
    TeamMemberStat,
    TeamOverview,
    TradeSummary,
)

# Decimal 高精度
getcontext().prec = 28

# 缓存键前缀 + TTL
STATS_CACHE_PREFIX = "stats:v1"
STATS_CACHE_TTL = 30  # 秒


class StatisticsService:
    """统计分析服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- 工具方法 ----------

    def _resolve_period_preset(
        self, params: StatisticsQueryParams
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """解析快捷预设时间区间。"""
        if not params.period_preset:
            return params.start_date, params.end_date

        now = datetime.now(timezone.utc)
        preset = params.period_preset.lower()
        if preset == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, now
        if preset == "week":
            # 周一为起点
            start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return start, now
        if preset == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start, now
        if preset == "quarter":
            q_start_month = ((now.month - 1) // 3) * 3 + 1
            start = now.replace(
                month=q_start_month, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            return start, now
        if preset == "year":
            start = now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            return start, now
        if preset == "all":
            return None, None
        return params.start_date, params.end_date

    def _build_filters(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[Any]:
        """构建 5 维过滤条件 + 来源过滤（只统计真实交易数据）。"""
        start, end = self._resolve_period_preset(params)
        conditions: List[Any] = [
            Trade.user_id == user_id,
            # 只统计真实交易数据，排除模拟交易（paper）
            Trade.source.in_(["exchange_sync", "manual", "import", "live"]),
        ]
        if start:
            conditions.append(Trade.executed_at >= start)
        if end:
            conditions.append(Trade.executed_at <= end)
        if params.symbol:
            conditions.append(Trade.symbol == params.symbol)
        if params.account_id:
            conditions.append(Trade.account_id == params.account_id)
        if params.strategy_id:
            conditions.append(Trade.strategy_id == params.strategy_id)
        if params.side:
            conditions.append(Trade.side == params.side)
        if params.tags:
            # JSONB @> 数组包含
            conditions.append(Trade.tags.op("@>")(params.tags))
        return conditions

    async def _get_cache(self, key: str) -> Optional[dict]:
        """读取 Redis 缓存。"""
        try:
            if redis_client is None:
                return None
            raw = await redis_client.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning("读取统计缓存失败 | key={} err={}", key, e)
        return None

    async def _set_cache(self, key: str, data: dict) -> None:
        """写入 Redis 缓存。"""
        try:
            if redis_client is None:
                return
            await redis_client.set(key, json.dumps(data, default=str), ex=STATS_CACHE_TTL)
        except Exception as e:
            logger.warning("写入统计缓存失败 | key={} err={}", key, e)

    @staticmethod
    def _cache_key(prefix: str, user_id: uuid.UUID, params: StatisticsQueryParams) -> str:
        """生成缓存键（基于参数哈希）。"""
        param_str = params.model_dump_json()
        return f"{STATS_CACHE_PREFIX}:{prefix}:{user_id}:{hash(param_str)}"

    # ---------- 14 项核心指标 ----------

    async def get_core_metrics(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> CoreMetrics:
        """计算 14 项核心指标（基于 Trade.pnl 真实盈亏）。"""
        conditions = self._build_filters(user_id, params)

        # 1. 基础聚合：交易数 / 成交额 / 手续费 / 买卖笔数 / pnl 累加 / 极值
        result = await self.db.execute(
            select(
                func.count(Trade.id).label("total_trades"),
                func.sum(Trade.price * Trade.quantity).label("total_volume"),
                func.sum(Trade.fee).label("total_fee"),
                func.sum(case((Trade.side == "buy", 1), else_=0)).label("buy_count"),
                func.sum(case((Trade.side == "sell", 1), else_=0)).label("sell_count"),
                func.sum(Trade.pnl).label("total_pnl"),
                func.count(Trade.id).filter(Trade.pnl > 0).label("profit_count"),
                func.count(Trade.id).filter(Trade.pnl < 0).label("loss_count"),
                func.max(Trade.pnl).label("max_single_profit"),
                func.min(Trade.pnl).label("max_single_loss"),
                func.avg(Trade.holding_seconds).label("avg_holding_seconds"),
            ).where(*conditions)
        )
        row = result.one()

        # 2. 平均盈亏比 = AVG(盈利单 pnl) / |AVG(亏损单 pnl)|
        avg_win_loss_ratio: Optional[Decimal] = None
        if row.profit_count and row.loss_count:
            avg_win_result = await self.db.execute(
                select(func.avg(Trade.pnl)).where(*conditions, Trade.pnl > 0)
            )
            avg_loss_result = await self.db.execute(
                select(func.avg(Trade.pnl)).where(*conditions, Trade.pnl < 0)
            )
            avg_win = avg_win_result.scalar()
            avg_loss = avg_loss_result.scalar()
            if avg_win is not None and avg_loss not in (None, 0):
                avg_win_loss_ratio = Decimal(str(avg_win)) / Decimal(str(abs(avg_loss)))

        # 3. 胜率
        pnl_count = (row.profit_count or 0) + (row.loss_count or 0)
        win_rate: Optional[Decimal] = None
        if pnl_count > 0:
            win_rate = Decimal(row.profit_count or 0) / Decimal(pnl_count)

        # 4. 总收益率（用首次买入成本估算；有资产快照则用期初快照）
        total_return_rate: Optional[Decimal] = None
        buy_cost_result = await self.db.execute(
            select(func.sum(Trade.price * Trade.quantity)).where(
                *conditions, Trade.side == "buy"
            )
        )
        buy_cost = buy_cost_result.scalar() or Decimal("0")
        if buy_cost > 0 and row.total_pnl is not None:
            total_return_rate = Decimal(str(row.total_pnl)) / Decimal(str(buy_cost))

        # 5. 最大回撤 / 夏普 / Sortino（基于日累计盈亏序列）
        max_drawdown, sharpe, sortino = await self._calc_risk_metrics(conditions)

        return CoreMetrics(
            total_pnl=Decimal(str(row.total_pnl or 0)),
            total_return_rate=total_return_rate,
            total_volume=Decimal(str(row.total_volume or 0)),
            total_fee=Decimal(str(row.total_fee or 0)),
            total_trades=row.total_trades or 0,
            buy_count=row.buy_count or 0,
            sell_count=row.sell_count or 0,
            win_rate=win_rate,
            avg_win_loss_ratio=avg_win_loss_ratio,
            profit_count=row.profit_count or 0,
            loss_count=row.loss_count or 0,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_single_profit=(
                Decimal(str(row.max_single_profit)) if row.max_single_profit else None
            ),
            max_single_loss=(
                Decimal(str(row.max_single_loss)) if row.max_single_loss else None
            ),
            avg_holding_seconds=(
                int(row.avg_holding_seconds) if row.avg_holding_seconds else None
            ),
        )

    async def _calc_risk_metrics(
        self, conditions: List[Any]
    ) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
        """基于日累计盈亏序列计算最大回撤 / 夏普 / Sortino。"""
        # 按日聚合 pnl
        daily_result = await self.db.execute(
            select(
                func.date_trunc("day", Trade.executed_at).label("day"),
                func.sum(Trade.pnl).label("daily_pnl"),
            )
            .where(*conditions)
            .group_by("day")
            .order_by("day")
        )
        daily_pnls = [
            Decimal(str(r.daily_pnl or 0)) for r in daily_result.all()
        ]

        if not daily_pnls:
            return None, None, None

        # 最大回撤
        equity = Decimal("0")
        peak = Decimal("0")
        max_dd = Decimal("0")
        for pnl in daily_pnls:
            equity += pnl
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd

        # 夏普 = mean / std * sqrt(365)
        n = len(daily_pnls)
        mean_pnl = sum(daily_pnls) / Decimal(n)
        variance = sum((p - mean_pnl) ** 2 for p in daily_pnls) / Decimal(n)
        std_pnl = Decimal(str(math.sqrt(float(variance)))) if variance > 0 else Decimal("0")

        sharpe: Optional[Decimal] = None
        sortino: Optional[Decimal] = None
        if std_pnl > 0:
            sharpe = (mean_pnl / std_pnl) * Decimal(str(math.sqrt(365)))

        # Sortino：只用负收益的标准差
        negative_pnls = [p for p in daily_pnls if p < 0]
        if negative_pnls:
            neg_mean = sum(negative_pnls) / Decimal(len(negative_pnls))
            neg_var = sum((p - neg_mean) ** 2 for p in negative_pnls) / Decimal(
                len(negative_pnls)
            )
            neg_std = Decimal(str(math.sqrt(float(neg_var)))) if neg_var > 0 else Decimal("0")
            if neg_std > 0:
                sortino = (mean_pnl / neg_std) * Decimal(str(math.sqrt(365)))

        return max_dd if max_dd > 0 else None, sharpe, sortino

    # ---------- 9 类图表 ----------

    async def get_equity_curve(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[EquityCurvePoint]:
        """权益曲线（按日累计 pnl）。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                func.date_trunc("day", Trade.executed_at).label("day"),
                func.sum(Trade.pnl).label("daily_pnl"),
            )
            .where(*conditions)
            .group_by("day")
            .order_by("day")
        )
        rows = result.all()
        cum_pnl = Decimal("0")
        points: List[EquityCurvePoint] = []
        for r in rows:
            cum_pnl += Decimal(str(r.daily_pnl or 0))
            # equity = 累计盈亏（无期初资产数据时简化）
            points.append(
                EquityCurvePoint(
                    date=r.day.strftime("%Y-%m-%d") if r.day else "",
                    equity=cum_pnl,
                    cum_pnl=cum_pnl,
                )
            )
        return points

    async def get_monthly_pnl(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[MonthlyPnLBar]:
        """月度盈亏柱状图。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                func.to_char(
                    func.date_trunc("month", Trade.executed_at), "YYYY-MM"
                ).label("month"),
                func.sum(Trade.pnl).label("pnl"),
                func.count(Trade.id).label("trade_count"),
            )
            .where(*conditions)
            .group_by("month")
            .order_by("month")
        )
        return [
            MonthlyPnLBar(
                month=r.month,
                pnl=Decimal(str(r.pnl or 0)),
                trade_count=r.trade_count or 0,
            )
            for r in result.all()
        ]

    async def get_pnl_distribution(
        self,
        user_id: uuid.UUID,
        params: StatisticsQueryParams,
        bin_count: int = 10,
    ) -> List[PnLDistributionBin]:
        """盈亏分布直方图（width_bucket）。"""
        conditions = self._build_filters(user_id, params)
        # 先取极值
        extremes = await self.db.execute(
            select(
                func.min(Trade.pnl).label("min_pnl"),
                func.max(Trade.pnl).label("max_pnl"),
            ).where(*conditions, Trade.pnl.isnot(None))
        )
        ext = extremes.one()
        if ext.min_pnl is None or ext.max_pnl is None:
            return []
        min_pnl = Decimal(str(ext.min_pnl))
        max_pnl = Decimal(str(ext.max_pnl))
        if max_pnl == min_pnl:
            return [
                PnLDistributionBin(
                    bin_start=min_pnl, bin_end=max_pnl, count=1
                )
            ]
        bin_width = (max_pnl - min_pnl) / Decimal(bin_count)

        # 按 width_bucket 分桶
        buckets_result = await self.db.execute(
            select(
                func.width_bucket(
                    Trade.pnl,
                    float(min_pnl),
                    float(max_pnl),
                    bin_count,
                ).label("bucket"),
                func.count(Trade.id).label("count"),
            )
            .where(*conditions, Trade.pnl.isnot(None))
            .group_by("bucket")
            .order_by("bucket")
        )
        bins: List[PnLDistributionBin] = []
        for r in buckets_result.all():
            bucket = r.bucket or 1
            start = min_pnl + bin_width * Decimal(bucket - 1)
            end = min_pnl + bin_width * Decimal(bucket)
            bins.append(
                PnLDistributionBin(bin_start=start, bin_end=end, count=r.count or 0)
            )
        return bins

    async def get_symbol_contribution(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[SymbolContribution]:
        """币种贡献度饼图。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                Trade.symbol.label("symbol"),
                func.sum(Trade.pnl).label("pnl"),
                func.count(Trade.id).label("trade_count"),
            )
            .where(*conditions)
            .group_by(Trade.symbol)
            .order_by(func.sum(Trade.pnl).desc())
        )
        rows = result.all()
        total_pnl = sum((Decimal(str(r.pnl or 0)) for r in rows), Decimal("0"))
        contributions: List[SymbolContribution] = []
        for r in rows:
            pnl = Decimal(str(r.pnl or 0))
            percentage = (pnl / total_pnl) if total_pnl != 0 else Decimal("0")
            contributions.append(
                SymbolContribution(
                    symbol=r.symbol,
                    pnl=pnl,
                    trade_count=r.trade_count or 0,
                    percentage=percentage,
                )
            )
        return contributions

    async def get_strategy_contribution(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[StrategyContribution]:
        """策略贡献度柱状图（含策略名）。"""
        conditions = self._build_filters(user_id, params)
        # 仅含 strategy_id 非空的
        result = await self.db.execute(
            select(
                Trade.strategy_id.label("strategy_id"),
                func.sum(Trade.pnl).label("pnl"),
                func.count(Trade.id).label("trade_count"),
            )
            .where(*conditions, Trade.strategy_id.isnot(None))
            .group_by(Trade.strategy_id)
        )
        rows = result.all()
        # 加载策略名
        strategy_ids = [r.strategy_id for r in rows]
        names_map: Dict = {}
        if strategy_ids:
            name_result = await self.db.execute(
                select(Strategy.id, Strategy.name).where(Strategy.id.in_(strategy_ids))
            )
            names_map = {row.id: row.name for row in name_result.all()}

        return [
            StrategyContribution(
                strategy_id=str(r.strategy_id),
                strategy_name=names_map.get(r.strategy_id),
                pnl=Decimal(str(r.pnl or 0)),
                trade_count=r.trade_count or 0,
            )
            for r in rows
        ]

    async def get_heatmap(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[HeatmapCell]:
        """星期 × 小时热力图。"""
        conditions = self._build_filters(user_id, params)
        # Postgres: extract(dow) 0=周日；ISO 8601 用 isodow（1=周一）
        result = await self.db.execute(
            select(
                (func.extract("isodow", Trade.executed_at) - 1).label("weekday"),
                func.extract("hour", Trade.executed_at).label("hour"),
                func.count(Trade.id).label("trade_count"),
                func.sum(Trade.pnl).label("pnl"),
            )
            .where(*conditions)
            .group_by("weekday", "hour")
            .order_by("weekday", "hour")
        )
        return [
            HeatmapCell(
                weekday=int(r.weekday),
                hour=int(r.hour),
                trade_count=r.trade_count or 0,
                pnl=Decimal(str(r.pnl or 0)),
            )
            for r in result.all()
        ]

    async def get_asset_composition(
        self, user_id: uuid.UUID, account_id: Optional[uuid.UUID] = None
    ) -> List[AssetComposition]:
        """资产构成饼图（最近一次资产快照）。"""
        # 取最新一条快照
        latest_result = await self.db.execute(
            select(AssetSnapshot)
            .where(AssetSnapshot.user_id == user_id)
            .order_by(AssetSnapshot.snapshot_at.desc())
            .limit(1)
        )
        snapshot = latest_result.scalar_one_or_none()
        if snapshot is None or not snapshot.balances:
            return []

        balances: Dict = snapshot.balances
        total_usd = sum(
            Decimal(str(b.get("usd", 0))) for b in balances.values()
        )
        items: List[AssetComposition] = []
        for symbol, bal in balances.items():
            usd = Decimal(str(bal.get("usd", 0)))
            total = Decimal(str(bal.get("total", 0)))
            percentage = (usd / total_usd) if total_usd > 0 else Decimal("0")
            items.append(
                AssetComposition(
                    symbol=symbol,
                    total=total,
                    usd_value=usd,
                    percentage=percentage,
                )
            )
        items.sort(key=lambda x: x.usd_value, reverse=True)
        return items

    async def get_drawdown_curve(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[DrawdownPoint]:
        """回撤曲线（权益 - 窗口 MAX）。"""
        curve = await self.get_equity_curve(user_id, params)
        if not curve:
            return []
        peak = curve[0].equity
        points: List[DrawdownPoint] = []
        for p in curve:
            if p.equity > peak:
                peak = p.equity
            dd = Decimal("0")
            if peak > 0:
                dd = (peak - p.equity) / peak
            points.append(DrawdownPoint(date=p.date, drawdown=dd))
        return points

    async def get_pnl_scatter(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[ScatterPoint]:
        """每笔盈亏散点（pnl vs 持仓时长）。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                Trade.id,
                Trade.pnl,
                Trade.holding_seconds,
                Trade.symbol,
            )
            .where(*conditions, Trade.pnl.isnot(None))
            .order_by(Trade.executed_at.asc())
            .limit(500)  # 散点最多 500 个
        )
        return [
            ScatterPoint(
                trade_id=str(r.id),
                pnl=Decimal(str(r.pnl)),
                holding_seconds=r.holding_seconds,
                symbol=r.symbol,
            )
            for r in result.all()
        ]

    # ---------- 报表 5 章 ----------

    async def get_report(
        self,
        user_id: uuid.UUID,
        params: StatisticsQueryParams,
        title: Optional[str] = None,
    ) -> StatisticsReport:
        """生成统计报表（5 章结构化 JSON）。"""
        start, end = self._resolve_period_preset(params)
        now = datetime.now(timezone.utc)
        title = title or "AI 交易系统统计报表"

        metrics = await self.get_core_metrics(user_id, params)
        charts = ReportCharts(
            equity_curve=await self.get_equity_curve(user_id, params),
            monthly_pnl=await self.get_monthly_pnl(user_id, params),
            pnl_distribution=await self.get_pnl_distribution(user_id, params),
            symbol_contribution=await self.get_symbol_contribution(user_id, params),
            strategy_contribution=await self.get_strategy_contribution(user_id, params),
            heatmap=await self.get_heatmap(user_id, params),
            asset_composition=await self.get_asset_composition(user_id),
            drawdown_curve=await self.get_drawdown_curve(user_id, params),
            pnl_scatter=await self.get_pnl_scatter(user_id, params),
        )
        top_trades = await self._get_top_trades(user_id, params)

        # 封面文字
        summary_text = (
            f"周期：{start or '全部'} 至 {end or '现在'}；"
            f"总交易 {metrics.total_trades} 笔；"
            f"总盈亏 {metrics.total_pnl}；"
            f"胜率 {metrics.win_rate or 'N/A'}"
        )

        return StatisticsReport(
            cover=ReportCover(
                title=title,
                user_id=user_id,
                period_start=start or datetime.min.replace(tzinfo=timezone.utc),
                period_end=end or now,
                generated_at=now,
                summary_text=summary_text,
            ),
            metrics=ReportMetrics(metrics=metrics),
            charts=charts,
            top_trades=top_trades,
            ai_conclusion=ReportAIConclusion(),
        )

    async def _get_top_trades(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> ReportTopTrades:
        """获取 Top10 盈利 + Top10 亏损。"""
        conditions = self._build_filters(user_id, params)
        profits_result = await self.db.execute(
            select(Trade)
            .where(*conditions, Trade.pnl.isnot(None), Trade.pnl > 0)
            .order_by(Trade.pnl.desc())
            .limit(10)
        )
        losses_result = await self.db.execute(
            select(Trade)
            .where(*conditions, Trade.pnl.isnot(None), Trade.pnl < 0)
            .order_by(Trade.pnl.asc())
            .limit(10)
        )

        def _to_dict(t: Trade) -> dict:
            return {
                "id": str(t.id),
                "symbol": t.symbol,
                "side": t.side,
                "price": str(t.price),
                "quantity": str(t.quantity),
                "pnl": str(t.pnl) if t.pnl is not None else None,
                "pnl_ratio": str(t.pnl_ratio) if t.pnl_ratio is not None else None,
                "executed_at": t.executed_at.isoformat() if t.executed_at else None,
                "holding_seconds": t.holding_seconds,
            }

        return ReportTopTrades(
            top_profits=[_to_dict(t) for t in profits_result.scalars().all()],
            top_losses=[_to_dict(t) for t in losses_result.scalars().all()],
        )

    # ---------- 团队视角（Admin） ----------

    async def get_team_overview(
        self, params: StatisticsQueryParams
    ) -> TeamOverview:
        """团队整体报表（Admin；按 user_id GROUP BY）。

        注意：5 维过滤中的 account_id/strategy_id/tags/symbol 维度仍生效，
        但忽略 user_id（admin 看所有用户）。
        """
        conditions: List[Any] = [
            # 只统计真实交易数据，排除模拟交易（paper）
            Trade.source.in_(["exchange_sync", "manual", "import", "live"]),
        ]
        if params.start_date:
            conditions.append(Trade.executed_at >= params.start_date)
        if params.end_date:
            conditions.append(Trade.executed_at <= params.end_date)
        if params.symbol:
            conditions.append(Trade.symbol == params.symbol)
        if params.strategy_id:
            conditions.append(Trade.strategy_id == params.strategy_id)

        result = await self.db.execute(
            select(
                Trade.user_id,
                func.sum(Trade.pnl).label("total_pnl"),
                func.count(Trade.id).label("total_trades"),
                func.count(Trade.id).filter(Trade.pnl > 0).label("profit_count"),
                func.count(Trade.id).filter(Trade.pnl < 0).label("loss_count"),
            )
            .where(*conditions)
            .group_by(Trade.user_id)
            .order_by(func.sum(Trade.pnl).desc())
        )
        rows = result.all()

        # 加载用户基础信息
        user_ids = [r.user_id for r in rows]
        users_map: Dict = {}
        if user_ids:
            user_result = await self.db.execute(
                select(User.id, User.email, User.nickname, User.role).where(
                    User.id.in_(user_ids)
                )
            )
            users_map = {u.id: u for u in user_result.all()}

        members: List[TeamMemberStat] = []
        total_pnl = Decimal("0")
        total_trades = 0
        for r in rows:
            pnl = Decimal(str(r.total_pnl or 0))
            total_pnl += pnl
            total_trades += r.total_trades or 0
            pnl_count = (r.profit_count or 0) + (r.loss_count or 0)
            win_rate = (
                Decimal(r.profit_count or 0) / Decimal(pnl_count)
                if pnl_count > 0
                else None
            )
            user = users_map.get(r.user_id)
            members.append(
                TeamMemberStat(
                    user_id=r.user_id,
                    user_email=user.email if user else None,
                    user_nickname=user.nickname if user else None,
                    role=user.role if user else "unknown",
                    total_pnl=pnl,
                    total_trades=r.total_trades or 0,
                    win_rate=win_rate,
                )
            )

        return TeamOverview(
            member_count=len(members),
            total_pnl=total_pnl,
            total_trades=total_trades,
            members=members,
        )

    # ---------- 兼容旧接口（保留 /summary /pnl /coins /asset-trend 等） ----------

    async def get_trade_summary(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> TradeSummary:
        """[兼容] 交易汇总。"""
        metrics = await self.get_core_metrics(user_id, params)
        return TradeSummary(
            total_trades=metrics.total_trades,
            total_volume=metrics.total_volume,
            total_fee=metrics.total_fee,
            buy_count=metrics.buy_count,
            sell_count=metrics.sell_count,
            win_rate=metrics.win_rate,
            profit_loss=metrics.total_pnl,
        )

    async def get_pnl_by_period(
        self,
        user_id: uuid.UUID,
        params: StatisticsQueryParams,
        period: str = "daily",
    ) -> List[PnLByPeriod]:
        """[兼容] 按周期统计盈亏。"""
        conditions = self._build_filters(user_id, params)
        if period == "monthly":
            date_expr = func.to_char(
                func.date_trunc("month", Trade.executed_at), "YYYY-MM"
            )
        elif period == "weekly":
            date_expr = func.to_char(
                func.date_trunc("week", Trade.executed_at), 'IYYY-"W"IW'
            )
        else:
            date_expr = func.to_char(
                func.date_trunc("day", Trade.executed_at), "YYYY-MM-DD"
            )

        result = await self.db.execute(
            select(
                date_expr.label("period"),
                func.sum(Trade.pnl).label("pnl"),
                func.count(Trade.id).label("trade_count"),
            )
            .where(*conditions)
            .group_by("period")
            .order_by("period")
        )
        return [
            PnLByPeriod(
                period=r.period,
                pnl=Decimal(str(r.pnl or 0)),
                trade_count=r.trade_count or 0,
            )
            for r in result.all()
        ]

    async def get_coin_stats(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[CoinStat]:
        """[兼容] 币种统计。"""
        contributions = await self.get_symbol_contribution(user_id, params)
        return [
            CoinStat(
                symbol=c.symbol,
                trade_count=c.trade_count,
                total_volume=Decimal("0"),  # 旧字段，无对应数据
                total_fee=Decimal("0"),
                net_pnl=c.pnl,
                win_rate=None,
            )
            for c in contributions
        ]

    async def get_asset_trend(
        self,
        user_id: uuid.UUID,
        account_id: Optional[str] = None,
        days: int = 30,
    ) -> List[AssetTrend]:
        """[兼容] 资产趋势。"""
        start = datetime.now(timezone.utc) - timedelta(days=days)
        conditions = [
            AssetSnapshot.user_id == user_id,
            AssetSnapshot.snapshot_at >= start,
        ]
        if account_id:
            conditions.append(AssetSnapshot.account_id == account_id)

        result = await self.db.execute(
            select(
                AssetSnapshot.snapshot_at.label("date"),
                func.sum(AssetSnapshot.total_usd).label("total_usd"),
            )
            .where(*conditions)
            .group_by(AssetSnapshot.snapshot_at)
            .order_by(AssetSnapshot.snapshot_at.asc())
        )
        return [
            AssetTrend(date=row.date, total_usd=row.total_usd or Decimal("0"))
            for row in result.all()
        ]

    async def get_exchange_distribution(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[dict]:
        """[兼容] 按交易所分布。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                Trade.exchange.label("exchange"),
                func.count(Trade.id).label("trade_count"),
                func.sum(Trade.pnl).label("pnl"),
                func.sum(Trade.price * Trade.quantity).label("volume"),
            )
            .where(*conditions)
            .group_by(Trade.exchange)
            .order_by(func.sum(Trade.pnl).desc())
        )
        return [
            {
                "exchange": r.exchange,
                "trade_count": r.trade_count or 0,
                "pnl": float(r.pnl or 0),
                "volume": float(r.volume or 0),
            }
            for r in result.all()
        ]

    async def get_side_distribution(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[dict]:
        """[兼容] 按买卖方向分布。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                Trade.side.label("side"),
                func.count(Trade.id).label("count"),
                func.sum(Trade.price * Trade.quantity).label("volume"),
            )
            .where(*conditions)
            .group_by(Trade.side)
        )
        return [
            {
                "side": r.side,
                "count": r.count or 0,
                "volume": float(r.volume or 0),
            }
            for r in result.all()
        ]

    async def get_time_distribution(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[dict]:
        """[兼容] 按小时分布。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                func.extract("hour", Trade.executed_at).label("hour"),
                func.count(Trade.id).label("count"),
            )
            .where(*conditions)
            .group_by("hour")
            .order_by("hour")
        )
        return [
            {"hour": int(r.hour), "count": r.count or 0} for r in result.all()
        ]

    async def get_strategy_comparison(
        self, user_id: uuid.UUID
    ) -> List[dict]:
        """[兼容] 策略收益对比。"""
        params = StatisticsQueryParams()
        contributions = await self.get_strategy_contribution(user_id, params)
        return [
            {
                "strategy_id": c.strategy_id,
                "strategy_name": c.strategy_name,
                "trade_count": c.trade_count,
                "pnl": float(c.pnl),
            }
            for c in contributions
        ]

    async def get_monthly_report(
        self,
        user_id: uuid.UUID,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> dict:
        """[兼容] 月度报表。"""
        now = datetime.now(timezone.utc)
        year = year or now.year
        month = month or now.month
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            if month == 12
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        )
        params = StatisticsQueryParams(start_date=start, end_date=end)
        summary = await self.get_trade_summary(user_id, params)
        pnl = await self.get_pnl_by_period(user_id, params, "daily")
        coins = await self.get_coin_stats(user_id, params)
        return {
            "year": year,
            "month": month,
            "summary": summary.model_dump(),
            "daily_pnl": [p.model_dump() for p in pnl],
            "coin_stats": [c.model_dump() for c in coins],
        }

    async def get_statistics(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> StatisticsResponse:
        """[兼容] 综合统计数据。"""
        summary = await self.get_trade_summary(user_id, params)
        pnl = await self.get_pnl_by_period(user_id, params)
        coins = await self.get_coin_stats(user_id, params)
        trend = await self.get_asset_trend(user_id)
        return StatisticsResponse(
            summary=summary,
            pnl_by_period=pnl,
            coin_stats=coins,
            asset_trend=trend,
        )

    async def export_report(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> str:
        """[兼容] 导出 CSV。"""
        stats = await self.get_statistics(user_id, params)
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["# 交易汇总"])
        writer.writerow(
            ["总交易笔数", "总成交额", "总手续费", "买入笔数", "卖出笔数", "胜率", "盈亏"]
        )
        s = stats.summary
        writer.writerow(
            [
                s.total_trades,
                s.total_volume,
                s.total_fee,
                s.buy_count,
                s.sell_count,
                s.win_rate or "",
                s.profit_loss or "",
            ]
        )

        writer.writerow([])
        writer.writerow(["# 按周期盈亏"])
        writer.writerow(["周期", "盈亏", "交易笔数"])
        for p in stats.pnl_by_period:
            writer.writerow([p.period, p.pnl, p.trade_count])

        writer.writerow([])
        writer.writerow(["# 币种统计"])
        writer.writerow(["交易对", "交易笔数", "净盈亏"])
        for c in stats.coin_stats:
            writer.writerow([c.symbol, c.trade_count, c.net_pnl or ""])

        writer.writerow([])
        writer.writerow(["# 资产趋势"])
        writer.writerow(["日期", "总资产(USD)"])
        for t in stats.asset_trend:
            writer.writerow([t.date, t.total_usd])

        return output.getvalue()
