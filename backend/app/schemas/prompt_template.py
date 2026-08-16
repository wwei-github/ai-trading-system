"""Prompt 模板 Pydantic Schema。"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PromptTemplateCreate(BaseModel):
    """创建 Prompt 模板请求。"""

    category: str = Field(
        ..., pattern=r"^(initial_analysis|backtest_precheck|deep_analysis)$",
        description="模板分类"
    )
    name: str = Field(..., max_length=200, description="模板名称")
    content: str = Field(..., description="模板内容（支持 {} 占位符）")
    is_active: bool = Field(default=True, description="是否启用")


class PromptTemplateUpdate(BaseModel):
    """更新 Prompt 模板请求。"""

    name: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class PromptTemplateResponse(BaseModel):
    """Prompt 模板响应。"""

    id: UUID
    category: str
    name: str
    content: str
    is_active: bool
    version: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PromptTemplateListResponse(BaseModel):
    """Prompt 模板列表项。"""

    id: UUID
    category: str
    name: str
    is_active: bool
    version: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}