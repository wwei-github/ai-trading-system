"""策略 Schema。"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StrategyBase(BaseModel):
    """策略基础字段。"""

    name: str = Field(..., description="策略名称")
    category: str = Field(..., description="策略类别")
    description: Optional[str] = None
    rules: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None


class StrategyCreate(StrategyBase):
    """创建策略请求。"""

    source_book_id: Optional[uuid.UUID] = None


class StrategyUpdate(BaseModel):
    """更新策略请求。"""

    name: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class StrategyResponse(StrategyBase):
    """策略响应。"""

    id: uuid.UUID
    user_id: uuid.UUID
    source_book_id: Optional[uuid.UUID] = None
    status: str
    is_template: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StrategyCloneRequest(BaseModel):
    """策略克隆请求。"""

    new_name: Optional[str] = Field(None, description="新策略名称，留空则使用「原名（副本）」")


# ---------- 回测 ----------


class BacktestBase(BaseModel):
    """回测基础字段。"""

    strategy_id: uuid.UUID
    symbol: str
    timeframe: str = "1d"
    start_date: date
    end_date: date
    initial_capital: Decimal = Decimal("10000.00")
    params: Optional[Dict[str, Any]] = None


class BacktestCreate(BacktestBase):
    """创建回测请求。"""

    pass


class BacktestResponse(BaseModel):
    """回测响应。"""

    id: uuid.UUID
    strategy_id: uuid.UUID
    symbol: str
    timeframe: str
    start_date: date
    end_date: date
    initial_capital: Decimal
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BacktestCompareRequest(BaseModel):
    """回测对比请求。"""

    backtest_id_a: uuid.UUID = Field(..., description="回测 A 的 ID")
    backtest_id_b: uuid.UUID = Field(..., description="回测 B 的 ID")


class BacktestTradeResponse(BaseModel):
    """回测交易明细响应。"""

    id: uuid.UUID
    backtest_id: uuid.UUID
    strategy_id: uuid.UUID
    symbol: str
    side: str
    entry_time: datetime
    entry_price: float
    quantity: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float
    pnl_pct: float
    holding_bars: int
    exit_reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- 模拟交易 ----------


class PaperTradingStartRequest(BaseModel):
    """启动模拟交易请求。"""

    strategy_id: uuid.UUID
    symbol: str = Field(..., description="交易对，如 BTC/USDT")
    timeframe: str = Field("1h", description="K 线周期")
    initial_capital: float = Field(10000.0, gt=0, description="初始虚拟资金（USDT）")


class PaperTradingControlRequest(BaseModel):
    """模拟交易控制请求。"""

    action: str = Field(..., description="操作：pause / resume / stop")


class PaperAccountResponse(BaseModel):
    """模拟交易账号响应。"""

    id: uuid.UUID
    user_id: uuid.UUID
    strategy_id: uuid.UUID
    symbol: str
    timeframe: str
    initial_capital: Decimal
    current_equity: Decimal
    available_cash: Decimal
    position: float
    avg_entry_price: Optional[float] = None
    status: str
    strategy_params: Optional[Dict[str, Any]] = None
    total_trades: int
    total_pnl: Decimal
    started_at: datetime
    stopped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaperTradeResponse(BaseModel):
    """模拟交易记录响应。"""

    id: uuid.UUID
    paper_account_id: uuid.UUID
    strategy_id: uuid.UUID
    user_id: uuid.UUID
    symbol: str
    side: str
    order_type: str
    price: float
    quantity: float
    fee: float
    executed_at: datetime
    signal_source: Optional[str] = None
    realized_pnl: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaperTradeRequest(BaseModel):
    """[兼容] 手动模拟交易请求（单笔）。"""

    symbol: str
    side: str  # buy / sell
    amount: float
    price: Optional[float] = None


# ---------- 策略规则结构化编辑（P1） ----------


class StrategyRuleCondition(BaseModel):
    """策略规则条件。"""

    indicator: str = Field(..., description="指标名，如 MA5、RSI、MACD")
    operator: str = Field(..., description="比较符：gt/lt/gte/lte/eq/cross_above/cross_below/custom")
    value: Any = Field(..., description="阈值或文本描述")
    description: Optional[str] = None


class StrategyRuleGroup(BaseModel):
    """规则组（支持 AND/OR 逻辑）。"""

    logic: str = Field("AND", description="AND / OR")
    conditions: List[StrategyRuleCondition] = Field(default_factory=list)


class StrategyRulesUpdate(BaseModel):
    """策略规则更新请求（仅更新规则相关字段）。"""

    entry_rules: Optional[List[StrategyRuleGroup]] = None
    exit_rules: Optional[List[StrategyRuleGroup]] = None
    position_sizing: Optional[Dict[str, Any]] = None
    risk_control: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None


class StrategyDetailResponse(StrategyResponse):
    """策略详情（含结构化规则字段）。"""

    entry_rules: List[StrategyRuleGroup] = Field(default_factory=list)
    exit_rules: List[StrategyRuleGroup] = Field(default_factory=list)
    position_sizing: Dict[str, Any] = Field(default_factory=dict)
    risk_control: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)


# ---------- 实盘交易 ----------


class LiveTradingStartRequest(BaseModel):
    """启动实盘策略实例请求。"""

    strategy_id: uuid.UUID
    account_id: uuid.UUID = Field(..., description="交易所账号 ID")
    symbol: str = Field(..., description="交易对，如 BTC/USDT")
    timeframe: str = Field("1h", description="K 线周期")
    mode: str = Field("semi_auto", description="运行模式：semi_auto / full_auto（V2）")
    risk_params: Optional[Dict[str, Any]] = Field(
        None, description="风控参数覆盖（不传则使用默认 8 阈值）"
    )


class LiveTradingStopRequest(BaseModel):
    """停止实盘策略请求。"""

    close_positions: bool = Field(
        False, description="True=停止并平所有仓；False=仅停止下单"
    )
    reason: Optional[str] = Field(None, description="停止原因")


class LiveOrderResponse(BaseModel):
    """实盘信号订单响应。"""

    id: uuid.UUID
    instance_id: uuid.UUID
    strategy_id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    symbol: str
    side: str
    order_type: str
    suggested_price: Optional[float] = None
    suggested_amount: float
    signal_strength: int
    reason: Optional[str] = None
    status: str
    signal_at: datetime
    confirmed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    exchange_order_id: Optional[str] = None
    executed_price: Optional[float] = None
    executed_amount: Optional[float] = None
    expires_at: Optional[datetime] = None
    risk_check_passed: Optional[bool] = None
    risk_reject_reason: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LiveTradeRequest(BaseModel):
    """[兼容] 直接实盘交易请求（需二次确认）。"""

    symbol: str
    side: str  # buy / sell
    order_type: str = "market"  # market / limit
    amount: float
    price: Optional[float] = None
    account_id: uuid.UUID
    confirm: bool = Field(False, description="必须为 true 才会执行实盘下单")
