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

    # ========== 08-AI回测K线分析优化 新增字段 ==========
    use_local_model: bool = Field(
        default=False, description="使用本地模型进行快速预筛"
    )
    local_model_klines: int = Field(
        default=10, ge=1, le=100, description="本地模型预筛时分析的 K 线数量"
    )
    strategy_ids: Optional[List[UUID]] = Field(
        default=None, description="多策略融合时，参与优化的策略 ID 列表"
    )


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

    # ========== 08-AI回测K线分析优化 新增字段 ==========
    parent_backtest_id: Optional[UUID] = None
    strategy_ids: Optional[List[UUID]] = None
    ai_call_count: Optional[int] = 0
    precheck_total: Optional[int] = 0
    precheck_triggered: Optional[int] = 0
    use_local_model: bool = False
    local_model_klines: int = 10
    initial_analysis: Optional[Dict[str, Any]] = None
    ai_analysis_logs: Optional[List[Dict[str, Any]]] = None
    prompt_template_ids: Optional[Dict[str, str]] = None

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

    # ========== 08-AI回测K线分析优化 新增字段 ==========
    ai_window_start: Optional[int] = None
    ai_window_end: Optional[int] = None
    trigger_reason: Optional[str] = None

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

    # ========== 08-AI回测K线分析优化 新增字段 ==========
    precheck_total: int = 0
    precheck_triggered: int = 0
    ai_call_count: int = 0
    current_stage_detail: str = ""  # precheck / deep_analysis / rule / suspended


class MergeOptimizeRequest(BaseModel):
    """多策略融合优化请求。"""

    name: str = Field(default="", description="融合后新策略名称")
    description: Optional[str] = Field(default=None, description="新策略描述")
    strategy_ids: List[UUID] = Field(..., min_length=2, description="要融合的策略 ID 列表")
    backtest_id: UUID = Field(..., description="作为父回测的 AI 回测 ID")
    timeframe: str = Field(default="15m", pattern=r"^(15m|1h|4h|1d)$")
    symbol: str = Field(default="BTC/USDT", max_length=20)


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

    # ========== 08-AI回测K线分析优化 新增字段 ==========
    use_local_model: bool = False
    ai_call_count: Optional[int] = 0
    precheck_total: Optional[int] = 0
    precheck_triggered: Optional[int] = 0
    parent_backtest_id: Optional[UUID] = None