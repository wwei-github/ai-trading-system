"""统计分析 Schema。"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StatisticsQueryParams(BaseModel):
    """统计查询参数。"""

    account_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    symbol: Optional[str] = None


class TradeSummary(BaseModel):
    """交易汇总统计。"""

    total_trades: int = 0
    total_volume: Decimal = Decimal("0")
    total_fee: Decimal = Decimal("0")
    buy_count: int = 0
    sell_count: int = 0
    win_rate: Optional[float] = None
    profit_loss: Optional[Decimal] = None


class PnLByPeriod(BaseModel):
    """按周期统计的盈亏。"""

    period: str
    pnl: Decimal
    trade_count: int


class CoinStat(BaseModel):
    """币种统计。"""

    symbol: str
    trade_count: int
    total_volume: Decimal
    total_fee: Decimal
    net_pnl: Optional[Decimal] = None
    win_rate: Optional[float] = None


class AssetTrend(BaseModel):
    """资产趋势。"""

    date: datetime
    total_usd: Decimal


class StatisticsResponse(BaseModel):
    """统计综合响应。"""

    summary: TradeSummary
    pnl_by_period: List[PnLByPeriod] = Field(default_factory=list)
    coin_stats: List[CoinStat] = Field(default_factory=list)
    asset_trend: List[AssetTrend] = Field(default_factory=list)
