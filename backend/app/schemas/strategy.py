"""策略 Schema。"""

import uuid
from datetime import datetime
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
    start_date: str
    end_date: str
    initial_capital: float = 10000.0
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
    start_date: str
    end_date: str
    initial_capital: float
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
