"""交易所账号 Schema。"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ExchangeAccountBase(BaseModel):
    """账号基础字段。"""

    exchange: str = Field(..., description="交易所名称（binance/okx/bybit/huobi/gate/coinbase）")
    label: str = Field(..., min_length=1, max_length=100, description="账号标签")
    api_key: str = Field(..., min_length=1, description="API Key（明文，传输后加密存储）")
    api_secret: str = Field(..., min_length=1, description="API Secret（明文）")
    passphrase: Optional[str] = Field(None, description="口令（OKX/Coinbase 必填）")
    permissions: Optional[List[str]] = Field(None, description="权限列表")
    is_testnet: bool = Field(False, description="是否为测试网")


class ExchangeAccountCreate(ExchangeAccountBase):
    """创建账号请求。"""

    pass


class ExchangeAccountUpdate(BaseModel):
    """更新账号请求。

    所有字段可选；如更新 api_key/api_secret/passphrase 会重新加密存储。
    """

    label: Optional[str] = Field(None, min_length=1, max_length=100)
    api_key: Optional[str] = Field(None, min_length=1, description="新 API Key（明文）")
    api_secret: Optional[str] = Field(None, min_length=1, description="新 API Secret（明文）")
    passphrase: Optional[str] = Field(None, description="新口令（明文）")
    permissions: Optional[List[str]] = None
    is_testnet: Optional[bool] = None
    status: Optional[str] = None
    is_enabled: Optional[bool] = None


class ExchangeAccountResponse(BaseModel):
    """账号响应（不包含敏感信息，API Key 脱敏显示）。"""

    id: uuid.UUID
    user_id: uuid.UUID
    exchange: str
    label: str
    api_key_masked: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_testnet: bool
    status: str
    is_enabled: bool
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionTestResponse(BaseModel):
    """连接测试响应。"""

    success: bool
    exchange: str
    is_testnet: bool
    latency_ms: Optional[int] = None
    permissions: Optional[List[str]] = None
    message: str = ""


class AccountToggleRequest(BaseModel):
    """账号启停请求。"""

    is_enabled: bool


class SupportedExchange(BaseModel):
    """受支持的交易所信息。"""

    name: str = Field(..., description="交易所名称（用于 API 字段）")
    requires_passphrase: bool = Field(..., description="是否需要 passphrase")
    supports_testnet: bool = Field(True, description="是否支持测试网")


class SupportedExchangesResponse(BaseModel):
    """受支持交易所列表响应。"""

    exchanges: List[SupportedExchange]
    total: int
