"""统计分析 Schema。

对齐 PRD §5.4.1 的 14 项核心指标 + §5.4.2 的 9 类图表 + §5.4.4 的 5 章报表结构。
所有金额/盈亏均使用 Decimal，避免浮点累计误差。
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------- 查询参数 ----------

class StatisticsQueryParams(BaseModel):
    """统计查询参数。

    支持 PRD §5.4.1 R1 的 5 维过滤：账号 / 策略 / 标签 / 币种 / 方向。
    + 时间范围（区间或快捷预设）。
    """

    account_id: Optional[uuid.UUID] = None
    strategy_id: Optional[uuid.UUID] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    tags: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    # 快捷预设：today/week/month/quarter/year/all
    # 与 start_date/end_date 二选一；同时传则预设被忽略
    period_preset: Optional[str] = None


# ---------- 14 项核心指标（PRD §5.4.1） ----------

class CoreMetrics(BaseModel):
    """14 项核心指标。

    口径严格按 PRD §5.4.1：
    1. PnL 总盈亏       = SUM(trade.pnl)
    2. 总收益率         = 总盈亏 / 期初资产（无快照则用首次买入成本）
    3. 交易次数         = COUNT(*)
    4. 胜率             = COUNT(pnl>0) / COUNT(pnl IS NOT NULL)
    5. 平均盈亏比       = AVG(盈利单 pnl / |亏损单 pnl|)
    6. 最大回撤         = max( (peak - equity) / peak )  滚动窗口
    7. 夏普比率         = AVG(daily_pnl) / STDDEV(daily_pnl) * sqrt(365)
    8. Sortino          = AVG(daily_pnl) / STDDEV(daily_pnl<0) * sqrt(365)
    9. 平均持仓时长(秒) = AVG(holding_seconds)  仅平仓单
    10. 盈利笔数
    11. 亏损笔数
    12. 最大单笔盈利
    13. 最大单笔亏损
    14. 总手续费
    """

    # 盈亏相关
    total_pnl: Decimal = Decimal("0")
    total_return_rate: Optional[Decimal] = None
    total_volume: Decimal = Decimal("0")
    total_fee: Decimal = Decimal("0")

    # 交易次数
    total_trades: int = 0
    buy_count: int = 0
    sell_count: int = 0

    # 胜率与盈亏比
    win_rate: Optional[Decimal] = None
    avg_win_loss_ratio: Optional[Decimal] = None
    profit_count: int = 0
    loss_count: int = 0

    # 风险指标
    max_drawdown: Optional[Decimal] = None
    sharpe_ratio: Optional[Decimal] = None
    sortino_ratio: Optional[Decimal] = None

    # 单笔极值
    max_single_profit: Optional[Decimal] = None
    max_single_loss: Optional[Decimal] = None

    # 持仓时长（秒）
    avg_holding_seconds: Optional[int] = None


# ---------- 9 类图表数据 ----------

class EquityCurvePoint(BaseModel):
    """权益曲线单点（按日聚合）。"""

    date: str  # YYYY-MM-DD
    equity: Decimal
    cum_pnl: Decimal
    benchmark: Optional[Decimal] = None  # BTC/ETH 基准（可选）


class MonthlyPnLBar(BaseModel):
    """月度盈亏柱状图。"""

    month: str  # YYYY-MM
    pnl: Decimal
    trade_count: int


class PnLDistributionBin(BaseModel):
    """盈亏分布直方图分桶。"""

    bin_start: Decimal
    bin_end: Decimal
    count: int


class SymbolContribution(BaseModel):
    """币种贡献度饼图。"""

    symbol: str
    pnl: Decimal
    trade_count: int
    percentage: Decimal  # 占总盈亏比例


class StrategyContribution(BaseModel):
    """策略贡献度柱状图。"""

    strategy_id: str
    strategy_name: Optional[str] = None
    pnl: Decimal
    trade_count: int


class HeatmapCell(BaseModel):
    """星期 × 小时热力图单元格。"""

    weekday: int  # 0=周一 ... 6=周日
    hour: int  # 0-23
    trade_count: int
    pnl: Decimal


class AssetComposition(BaseModel):
    """资产构成饼图（最近一次快照）。"""

    symbol: str
    total: Decimal
    usd_value: Decimal
    percentage: Decimal


class DrawdownPoint(BaseModel):
    """回撤曲线单点。"""

    date: str
    drawdown: Decimal


class ScatterPoint(BaseModel):
    """每笔盈亏散点（pnl vs 持仓时长）。"""

    trade_id: str
    pnl: Decimal
    holding_seconds: Optional[int] = None
    symbol: str


# ---------- 报表 5 章（PRD §5.4.4） ----------

class ReportCover(BaseModel):
    """报表封面。"""

    title: str
    user_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    summary_text: str  # 简要文字描述


class ReportMetrics(BaseModel):
    """报表第 2 章：核心指标。"""

    metrics: CoreMetrics


class ReportCharts(BaseModel):
    """报表第 3 章：图表数据。"""

    equity_curve: List[EquityCurvePoint] = Field(default_factory=list)
    monthly_pnl: List[MonthlyPnLBar] = Field(default_factory=list)
    pnl_distribution: List[PnLDistributionBin] = Field(default_factory=list)
    symbol_contribution: List[SymbolContribution] = Field(default_factory=list)
    strategy_contribution: List[StrategyContribution] = Field(default_factory=list)
    heatmap: List[HeatmapCell] = Field(default_factory=list)
    asset_composition: List[AssetComposition] = Field(default_factory=list)
    drawdown_curve: List[DrawdownPoint] = Field(default_factory=list)
    pnl_scatter: List[ScatterPoint] = Field(default_factory=list)


class ReportTopTrades(BaseModel):
    """报表第 4 章：Top10 盈亏明细。"""

    top_profits: List[dict] = Field(default_factory=list)
    top_losses: List[dict] = Field(default_factory=list)


class ReportAIConclusion(BaseModel):
    """报表第 5 章：AI 总结（V1 占位）。"""

    conclusion: str = "（V1 占位：AI 总结将在 V1.3 接入 LLM 后生成）"
    suggestions: List[str] = Field(default_factory=list)


class StatisticsReport(BaseModel):
    """统计报表 5 章完整结构。"""

    cover: ReportCover
    metrics: ReportMetrics
    charts: ReportCharts
    top_trades: ReportTopTrades
    ai_conclusion: ReportAIConclusion


# ---------- 兼容旧 schema（避免破坏现有前端） ----------

class TradeSummary(BaseModel):
    """[兼容] 交易汇总（已迁移到 CoreMetrics，保留旧字段供旧前端）。"""

    total_trades: int = 0
    total_volume: Decimal = Decimal("0")
    total_fee: Decimal = Decimal("0")
    buy_count: int = 0
    sell_count: int = 0
    win_rate: Optional[Decimal] = None
    profit_loss: Optional[Decimal] = None


class PnLByPeriod(BaseModel):
    """[兼容] 按周期统计的盈亏。"""

    period: str
    pnl: Decimal
    trade_count: int


class CoinStat(BaseModel):
    """[兼容] 币种统计。"""

    symbol: str
    trade_count: int
    total_volume: Decimal
    total_fee: Decimal
    net_pnl: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None


class AssetTrend(BaseModel):
    """[兼容] 资产趋势。"""

    date: datetime
    total_usd: Decimal


class StatisticsResponse(BaseModel):
    """[兼容] 统计综合响应。"""

    summary: TradeSummary
    pnl_by_period: List[PnLByPeriod] = Field(default_factory=list)
    coin_stats: List[CoinStat] = Field(default_factory=list)
    asset_trend: List[AssetTrend] = Field(default_factory=list)


# ---------- 团队视角（Admin） ----------

class TeamMemberStat(BaseModel):
    """团队成员统计（Admin 视角）。"""

    user_id: uuid.UUID
    user_email: Optional[str] = None
    user_nickname: Optional[str] = None
    role: str
    total_pnl: Decimal
    total_trades: int
    win_rate: Optional[Decimal] = None


class TeamOverview(BaseModel):
    """团队整体报表（Admin）。"""

    member_count: int
    total_pnl: Decimal
    total_trades: int
    members: List[TeamMemberStat] = Field(default_factory=list)
