"""交易所账号 Schema。"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ExchangeAccountBase(BaseModel):
    """账号基础字段。"""

    exchange: str = Field(..., description="交易所名称")
    label: str = Field(..., description="账号标签")
    api_key: str = Field(..., description="API Key（明文，传输后加密存储）")
    api_secret: str = Field(..., description="API Secret（明文）")
    passphrase: Optional[str] = Field(None, description="口令（OKX 等）")
    permissions: Optional[List[str]] = Field(None, description="权限列表")
    is_testnet: bool = Field(False, description="是否为测试网")


class ExchangeAccountCreate(ExchangeAccountBase):
    """创建账号请求。"""

    pass


class ExchangeAccountUpdate(BaseModel):
    """更新账号请求。"""

    label: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_testnet: Optional[bool] = None
    status: Optional[str] = None


class ExchangeAccountResponse(BaseModel):
    """账号响应（不包含敏感信息）。"""

    id: uuid.UUID
    user_id: uuid.UUID
    exchange: str
    label: str
    permissions: Optional[List[str]] = None
    is_testnet: bool
    status: str
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
