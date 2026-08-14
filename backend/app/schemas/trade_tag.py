"""交易标签 Schema。"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TradeTagCreate(BaseModel):
    """创建标签。"""

    name: str = Field(..., min_length=1, max_length=50, description="标签名")
    color: str = Field("#1890ff", max_length=20, description="颜色（HEX）")


class TradeTagUpdate(BaseModel):
    """更新标签。"""

    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, max_length=20)


class TradeTagResponse(BaseModel):
    """标签响应。"""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    color: str
    usage_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TradeTagMergeRequest(BaseModel):
    """标签合并请求。

    将 source_tags 中的所有标签合并到 target_tag，
    源标签会被删除，交易记录中的标签引用会被替换。
    """

    source_tag_ids: List[uuid.UUID] = Field(
        ..., min_length=1, description="待合并的源标签 ID 列表"
    )
    target_tag_id: uuid.UUID = Field(..., description="合并目标标签 ID")


class TradeTagMergeResponse(BaseModel):
    """标签合并响应。"""

    merged_count: int
    updated_trades: int
    deleted_tags: int
