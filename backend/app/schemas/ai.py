"""AI 助手 Schema。"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AIConversationCreate(BaseModel):
    """创建 AI 会话请求。"""

    mode: str = Field("general", description="会话模式")
    title: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class AIConversationResponse(BaseModel):
    """AI 会话响应。"""

    id: uuid.UUID
    user_id: uuid.UUID
    mode: str
    title: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AIMessageCreate(BaseModel):
    """发送 AI 消息请求。"""

    content: str = Field(..., description="消息内容")
    context: Optional[Dict[str, Any]] = None


class AIMessageResponse(BaseModel):
    """AI 消息响应。"""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    tokens_used: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AIChatResponse(BaseModel):
    """AI 聊天完整响应（包含用户消息和 AI 回复）。"""

    user_message: AIMessageResponse
    assistant_message: AIMessageResponse
