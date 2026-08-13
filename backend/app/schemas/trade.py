"""交易记录 Schema。"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class TradeResponse(BaseModel):
    """交易记录响应。"""

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    exchange: str
    symbol: str
    market_type: str
    side: str
    order_type: str
    price: Decimal
    quantity: Decimal
    leverage: Optional[int] = None
    fee: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    status: str
    strategy_id: Optional[uuid.UUID] = None
    tags: Optional[List[str]] = None
    note: Optional[str] = None
    exchange_order_id: Optional[str] = None
    executed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class TradeQueryParams(BaseModel):
    """交易记录查询参数。"""

    exchange: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    status: Optional[str] = None
    strategy_id: Optional[uuid.UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class TradeTagUpdate(BaseModel):
    """交易标签更新。"""

    tags: List[str] = Field(default_factory=list)
    note: Optional[str] = None
