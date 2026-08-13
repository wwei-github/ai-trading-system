"""币种分析 Schema。"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CoinInfo(BaseModel):
    """币种基本信息。"""

    symbol: str
    name: Optional[str] = None
    current_price: Optional[Decimal] = None
    price_change_24h: Optional[float] = None
    volume_24h: Optional[Decimal] = None


class CoinAnalysis(BaseModel):
    """币种技术分析。"""

    symbol: str
    timeframe: str
    indicators: Dict[str, float] = Field(default_factory=dict)
    signal: Optional[str] = None
    updated_at: Optional[datetime] = None


class CoinQueryParams(BaseModel):
    """币种查询参数。"""

    symbol: Optional[str] = None
    timeframe: str = Field("1d", description="时间周期")
    limit: int = Field(100, ge=1, le=1000)
