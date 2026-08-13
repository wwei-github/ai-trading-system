"""AI 助手 Schema。"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AIConversationCreate(BaseModel):
    """创建 AI 会话请求。"""

    mode: str = Field("general", description="会话模式：trade_analysis/strategy/book_qa/general/report")
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
    updated_at: datetime

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


class AISignalRequest(BaseModel):
    """AI 生成交易信号请求。"""

    symbol: str = Field(..., description="交易对")
    strategy_id: Optional[uuid.UUID] = None
    context: Optional[Dict[str, Any]] = None


class AISignalResponse(BaseModel):
    """AI 生成交易信号响应。"""

    symbol: str
    side: str  # buy / sell / hold
    strength: float  # 0.0 ~ 1.0
    reason: str
    strategy_id: Optional[uuid.UUID] = None


class AIReportRequest(BaseModel):
    """AI 生成分析报告请求。"""

    report_type: str = Field("trade", description="报告类型：trade/strategy/portfolio")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class AIReportResponse(BaseModel):
    """AI 生成分析报告响应。"""

    report_type: str
    title: str
    content: str
    generated_at: datetime
