"""策略 Schema。"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


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


class PaperTradeRequest(BaseModel):
    """模拟交易请求。"""

    symbol: str
    side: str  # buy / sell
    amount: float
    price: Optional[float] = None


class LiveTradeRequest(BaseModel):
    """实盘交易请求（需二次确认）。"""

    symbol: str
    side: str  # buy / sell
    order_type: str = "market"  # market / limit
    amount: float
    price: Optional[float] = None
    account_id: uuid.UUID
    confirm: bool = Field(False, description="必须为 true 才会执行实盘下单")
