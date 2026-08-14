"""AI 回测 Pydantic Schema。"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AIBacktestCreate(BaseModel):
    """创建 AI 回测请求。"""

    strategy_id: UUID
    symbol: str = Field(default="BTC/USDT", max_length=20)
    timeframe: str = Field(default="15m", pattern=r"^(15m|1h|4h|1d)$")
    start_time: datetime
    mode: str = Field(default="kline_count", pattern=r"^(kline_count|time_span)$")
    kline_count: Optional[int] = Field(default=None, ge=1, le=5000)
    time_span_value: Optional[int] = Field(default=None, ge=1, le=365)
    time_span_unit: Optional[str] = Field(default="day", pattern=r"^(hour|day)$")
    initial_capital: float = Field(default=10000.0, ge=100, le=100_000_000)
    fee_rate: float = Field(default=0.001, ge=0, le=0.01)
    use_ai: bool = True


class AIBacktestResponse(BaseModel):
    """AI 回测响应。"""

    id: UUID
    strategy_id: UUID
    strategy_name: str = ""
    symbol: str
    timeframe: str
    start_time: datetime
    end_time: Optional[datetime] = None
    mode: str
    kline_count: Optional[int] = None
    time_span_value: Optional[int] = None
    time_span_unit: Optional[str] = None
    initial_capital: float
    fee_rate: float
    use_ai: bool
    status: str
    total_klines: int
    completed_klines: int
    progress: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_summary: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AIBacktestTradeResponse(BaseModel):
    """AI 回测交易明细响应。"""

    id: UUID
    index: int
    direction: str
    entry_time: datetime
    entry_price: float
    quantity: float
    open_ai_analysis: Optional[str] = None
    open_reason: Optional[str] = None
    open_confidence: Optional[int] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    exit_ai_analysis: Optional[str] = None
    exit_confidence: Optional[int] = None
    holding_bars: Optional[int] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    fee: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AIBacktestProgress(BaseModel):
    """SSE 进度推送数据。"""

    backtest_id: str
    stage: str  # preheat / running / summary / done / error
    progress: float
    current_kline: int
    total_klines: int
    current_trades: int = 0
    current_position: Optional[Dict[str, Any]] = None
    message: str = ""


class AIBacktestListResponse(BaseModel):
    """AI 回测历史列表项。"""

    id: UUID
    strategy_name: str
    symbol: str
    timeframe: str
    status: str
    total_klines: int
    completed_klines: int
    initial_capital: float
    total_pnl: Optional[float] = None
    win_rate: Optional[float] = None
    trade_count: int = 0
    created_at: datetime
    completed_at: Optional[datetime] = None