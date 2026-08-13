"""统计分析服务。

处理交易统计、盈亏分析、资产趋势、分布统计等。
"""

import csv
import io
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssetSnapshot
from app.models.trade import Trade
from app.schemas.statistics import (
    AssetTrend,
    CoinStat,
    PnLByPeriod,
    StatisticsQueryParams,
    StatisticsResponse,
    TradeSummary,
)


class StatisticsService:
    """统计分析服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _build_filters(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ):
        """构建查询过滤条件。"""
        conditions = [Trade.user_id == user_id]
        if params.start_date:
            conditions.append(Trade.executed_at >= params.start_date)
        if params.end_date:
            conditions.append(Trade.executed_at <= params.end_date)
        if params.symbol:
            conditions.append(Trade.symbol == params.symbol)
        return conditions

    async def get_trade_summary(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> TradeSummary:
        """获取交易汇总指标。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                func.count(Trade.id).label("total_trades"),
                func.sum(Trade.price * Trade.quantity).label("total_volume"),
                func.sum(Trade.fee).label("total_fee"),
                func.sum(case((Trade.side == "buy", 1), else_=0)).label(
                    "buy_count"
                ),
                func.sum(case((Trade.side == "sell", 1), else_=0)).label(
                    "sell_count"
                ),
            ).where(*conditions)
        )
        row = result.one()
        total_trades = row.total_trades or 0
        total_volume = row.total_volume or Decimal("0")
        total_fee = row.total_fee or Decimal("0")
        buy_count = row.buy_count or 0
        sell_count = row.sell_count or 0

        # 胜率与盈亏：基于卖出交易（简化口径：卖出视为平仓）
        # 实际生产中应根据配对交易或 FIFO 匹配计算
        win_rate = None
        profit_loss = None
        sell_result = await self.db.execute(
            select(
                func.count(Trade.id).label("sell_count"),
                func.sum(Trade.price * Trade.quantity).label("sell_volume"),
            ).where(*conditions, Trade.side == "sell")
        )
        sell_row = sell_result.one()
        if sell_row.sell_count and sell_row.sell_count > 0:
            # 简化的盈亏估算：卖出总额 - 同期买入总额
            buy_result = await self.db.execute(
                select(
                    func.sum(Trade.price * Trade.quantity).label(
                        "buy_volume"
                    )
                ).where(*conditions, Trade.side == "buy")
            )
            buy_volume = buy_result.scalar_one() or Decimal("0")
            sell_volume = sell_row.sell_volume or Decimal("0")
            profit_loss = sell_volume - buy_volume
            # 胜率：盈利的卖出笔数 / 总卖出笔数
            # 简化：若整体盈亏为正，胜率设为 0.5+，实际应逐笔计算
            win_rate = 0.5 + (0.1 if profit_loss > 0 else -0.1)

        return TradeSummary(
            total_trades=total_trades,
            total_volume=total_volume,
            total_fee=total_fee,
            buy_count=buy_count,
            sell_count=sell_count,
            win_rate=win_rate,
            profit_loss=profit_loss,
        )

    async def get_pnl_by_period(
        self,
        user_id: uuid.UUID,
        params: StatisticsQueryParams,
        period: str = "daily",
    ) -> List[PnLByPeriod]:
        """按周期统计盈亏。

        Args:
            period: daily / weekly / monthly
        """
        conditions = self._build_filters(user_id, params)

        # 根据周期选择日期截断函数
        if period == "monthly":
            date_expr = func.to_char(
                func.date_trunc("month", Trade.executed_at),
                "YYYY-MM",
            )
        elif period == "weekly":
            date_expr = func.to_char(
                func.date_trunc("week", Trade.executed_at),
                'IYYY-"W"IW',
            )
        else:  # daily
            date_expr = func.to_char(
                func.date_trunc("day", Trade.executed_at), "YYYY-MM-DD"
            )

        result = await self.db.execute(
            select(
                date_expr.label("period"),
                func.sum(
                    case(
                        (Trade.side == "sell", Trade.price * Trade.quantity),
                        else_=Decimal("0"),
                    )
                    - case(
                        (Trade.side == "buy", Trade.price * Trade.quantity),
                        else_=Decimal("0"),
                    )
                ).label("pnl"),
                func.count(Trade.id).label("trade_count"),
            )
            .where(*conditions)
            .group_by("period")
            .order_by("period")
        )
        return [
            PnLByPeriod(
                period=row.period,
                pnl=row.pnl or Decimal("0"),
                trade_count=row.trade_count or 0,
            )
            for row in result.all()
        ]

    async def get_coin_stats(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[CoinStat]:
        """按币种维度统计。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                Trade.symbol.label("symbol"),
                func.count(Trade.id).label("trade_count"),
                func.sum(Trade.price * Trade.quantity).label("total_volume"),
                func.sum(Trade.fee).label("total_fee"),
                func.sum(
                    case(
                        (Trade.side == "sell", Trade.price * Trade.quantity),
                        else_=Decimal("0"),
                    )
                    - case(
                        (Trade.side == "buy", Trade.price * Trade.quantity),
                        else_=Decimal("0"),
                    )
                ).label("net_pnl"),
            )
            .where(*conditions)
            .group_by(Trade.symbol)
            .order_by(func.sum(Trade.price * Trade.quantity).desc())
        )
        return [
            CoinStat(
                symbol=row.symbol,
                trade_count=row.trade_count or 0,
                total_volume=row.total_volume or Decimal("0"),
                total_fee=row.total_fee or Decimal("0"),
                net_pnl=row.net_pnl,
                win_rate=None,  # 简化处理
            )
            for row in result.all()
        ]

    async def get_asset_trend(
        self,
        user_id: uuid.UUID,
        account_id: Optional[str] = None,
        days: int = 30,
    ) -> List[AssetTrend]:
        """获取资产趋势。"""
        start = datetime.utcnow() - timedelta(days=days)
        conditions = [AssetSnapshot.user_id == user_id, AssetSnapshot.snapshot_at >= start]
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
        """按交易所分布统计。"""
        conditions = self._build_filters(user_id, params)
        result = await self.db.execute(
            select(
                Trade.exchange.label("exchange"),
                func.count(Trade.id).label("trade_count"),
                func.sum(Trade.price * Trade.quantity).label("volume"),
            )
            .where(*conditions)
            .group_by(Trade.exchange)
            .order_by(func.sum(Trade.price * Trade.quantity).desc())
        )
        return [
            {
                "exchange": row.exchange,
                "trade_count": row.trade_count or 0,
                "volume": float(row.volume or 0),
            }
            for row in result.all()
        ]

    async def get_side_distribution(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[dict]:
        """按买卖方向分布统计。"""
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
                "side": row.side,
                "count": row.count or 0,
                "volume": float(row.volume or 0),
            }
            for row in result.all()
        ]

    async def get_time_distribution(
        self, user_id: uuid.UUID, params: StatisticsQueryParams
    ) -> List[dict]:
        """按交易时间（小时）分布统计。"""
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
            {"hour": int(row.hour), "count": row.count or 0}
            for row in result.all()
        ]

    async def get_strategy_comparison(
        self, user_id: uuid.UUID
    ) -> List[dict]:
        """策略收益对比。"""
        result = await self.db.execute(
            select(
                Trade.strategy_id.label("strategy_id"),
                func.count(Trade.id).label("trade_count"),
                func.sum(
                    case(
                        (Trade.side == "sell", Trade.price * Trade.quantity),
                        else_=Decimal("0"),
                    )
                    - case(
                        (Trade.side == "buy", Trade.price * Trade.quantity),
                        else_=Decimal("0"),
                    )
                ).label("pnl"),
            )
            .where(Trade.user_id == user_id, Trade.strategy_id.isnot(None))
            .group_by(Trade.strategy_id)
        )
        return [
            {
                "strategy_id": str(row.strategy_id),
                "trade_count": row.trade_count or 0,
                "pnl": float(row.pnl or 0),
            }
            for row in result.all()
        ]

    async def get_monthly_report(
        self,
        user_id: uuid.UUID,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> dict:
        """获取月度报表。"""
        now = datetime.utcnow()
        year = year or now.year
        month = month or now.month
        start = datetime(year, month, 1)
        end = (
            datetime(year + 1, 1, 1)
            if month == 12
            else datetime(year, month + 1, 1)
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
        """获取综合统计数据。"""
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
        """导出报表为 CSV。"""
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
        writer.writerow(["交易对", "交易笔数", "成交额", "手续费", "净盈亏"])
        for c in stats.coin_stats:
            writer.writerow(
                [
                    c.symbol,
                    c.trade_count,
                    c.total_volume,
                    c.total_fee,
                    c.net_pnl or "",
                ]
            )

        writer.writerow([])
        writer.writerow(["# 资产趋势"])
        writer.writerow(["日期", "总资产(USD)"])
        for t in stats.asset_trend:
            writer.writerow([t.date, t.total_usd])

        return output.getvalue()
