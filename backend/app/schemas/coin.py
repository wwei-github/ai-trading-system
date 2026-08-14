"""币种分析 Schema。

Stage 5 完整实现（对齐 PRD §5.5）：
- CoinInfo / TickerInfo：币种元信息 + 实时行情
- KlineItem / KlineResponse：K 线数据
- IndicatorResponse：14 类技术指标
- CompareResponse：多币种对比（归一化收益 + 相关性矩阵）
- AnalysisReport：AI 分析报告 6 部分结构
- WatchlistItem：用户自选
"""

import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------- 币种元信息 + 实时行情 ----------

class CoinInfo(BaseModel):
    """币种基本信息（含实时行情）。"""

    symbol: str
    name: Optional[str] = None
    current_price: Optional[Decimal] = None
    price_change_24h: Optional[float] = None  # 百分比，如 2.35 表示 +2.35%
    volume_24h: Optional[Decimal] = None  # 24h 成交额（quote volume）
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None
    exchange: Optional[str] = None  # 数据来源交易所


class TickerInfo(BaseModel):
    """实时行情（/coins/{symbol}/ticker 专用）。"""

    symbol: str
    name: str
    current_price: Optional[Decimal] = None
    price_change_24h: Optional[float] = None
    volume_24h: Optional[Decimal] = None
    timestamp: Optional[int] = None  # 毫秒时间戳


# ---------- K 线 ----------

class KlineItem(BaseModel):
    """K 线单根（OHLCV）。"""

    timestamp: int  # 毫秒时间戳（K 线开盘时间）
    open: float
    high: float
    low: float
    close: float
    volume: float


class KlineResponse(BaseModel):
    """K 线响应（含元信息）。"""

    symbol: str
    timeframe: str
    data: List[KlineItem] = Field(default_factory=list)
    source: str = "ccxt"  # ccxt / db / cache
    last_updated: Optional[datetime.datetime] = None


# ---------- 技术指标 ----------

class IndicatorResponse(BaseModel):
    """技术指标响应。"""

    symbol: str
    timeframe: str
    indicators: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    calculated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


# 兼容旧字段（CoinAnalysis）
class CoinAnalysis(BaseModel):
    """[兼容] 币种技术分析。"""

    symbol: str
    timeframe: str
    indicators: Dict[str, Any] = Field(default_factory=dict)
    signal: Optional[str] = None
    updated_at: Optional[datetime.datetime] = None


# ---------- 多币种对比 ----------

class ComparePoint(BaseModel):
    """归一化收益曲线单点。"""

    date: str  # YYYY-MM-DD
    values: Dict[str, float]  # {symbol: normalized_return}


class CorrelationMatrix(BaseModel):
    """相关性矩阵（N×N Pearson）。"""

    symbols: List[str]
    matrix: List[List[float]]  # 下三角对称


class CompareResponse(BaseModel):
    """多币种对比响应。"""

    symbols: List[str]
    days: int
    normalized_curve: List[ComparePoint] = Field(default_factory=list)
    correlation: Optional[CorrelationMatrix] = None
    summary: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    # summary = {symbol: {return_pct, volatility, sharpe}}


# ---------- AI 分析报告 ----------

class AnalysisTrend(BaseModel):
    """趋势判断。"""

    short_term: str  # bullish / bearish / neutral
    mid_term: str
    long_term: str
    description: str


class SupportResistance(BaseModel):
    """支撑阻力位。"""

    supports: List[float] = Field(default_factory=list)
    resistances: List[float] = Field(default_factory=list)
    fibonacci_levels: Dict[str, float] = Field(default_factory=dict)
    # {0.382: value, 0.5: value, 0.618: value}


class IndicatorSignals(BaseModel):
    """指标信号汇总。"""

    ma_signal: str  # bullish / bearish / neutral
    rsi_signal: str  # overbought / oversold / neutral
    macd_signal: str
    boll_signal: str
    summary: str


class VolumePriceFeature(BaseModel):
    """量价特征解读。"""

    volume_trend: str  # increasing / decreasing / stable
    price_volume_divergence: bool
    description: str


class RiskAssessment(BaseModel):
    """风险评估。"""

    volatility: float  # 年化波动率
    volatility_zscore: float  # 相对历史 z-score
    liquidity_score: Optional[float] = None  # 0-100
    description: str


class AnalysisRecommendation(BaseModel):
    """操作建议。"""

    action: str  # 观察 / 轻仓尝试 / 不推荐
    confidence: float  # 0-1
    reason: str
    disclaimer: str = "本报告基于规则计算，非投资建议，据此交易风险自负"


class AnalysisReport(BaseModel):
    """AI 分析报告（6 部分结构，对齐 PRD §5.5.4）。"""

    symbol: str
    timeframe: str = "1d"
    generated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    trend: Optional[AnalysisTrend] = None
    support_resistance: Optional[SupportResistance] = None
    indicator_signals: Optional[IndicatorSignals] = None
    volume_price: Optional[VolumePriceFeature] = None
    risk: Optional[RiskAssessment] = None
    recommendation: Optional[AnalysisRecommendation] = None


# ---------- 用户自选 ----------

class WatchlistItem(BaseModel):
    """用户自选项。"""

    id: str
    user_id: str
    symbol: str
    note: Optional[str] = None
    sort_order: int = 100
    added_price: Optional[float] = None
    created_at: datetime.datetime
    # 实时行情（可选，列表展示用）
    current_price: Optional[Decimal] = None
    price_change_24h: Optional[float] = None
    price_change_since_added: Optional[float] = None  # 自添加以来涨跌幅


class WatchlistCreate(BaseModel):
    """添加自选请求。"""

    symbol: str = Field(..., description="交易对，如 BTC/USDT")
    note: Optional[str] = Field(None, max_length=200)
    sort_order: int = Field(100, ge=0, le=10000)


class WatchlistUpdate(BaseModel):
    """更新自选请求。"""

    note: Optional[str] = Field(None, max_length=200)
    sort_order: Optional[int] = Field(None, ge=0, le=10000)


# ---------- 查询参数 ----------

class CoinQueryParams(BaseModel):
    """[兼容] 币种查询参数。"""

    symbol: Optional[str] = None
    timeframe: str = Field("1d", description="时间周期")
    limit: int = Field(100, ge=1, le=1000)
