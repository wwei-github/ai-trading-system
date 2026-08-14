"""AI 会话与消息模型。"""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AIConversation(Base):
    """AI 会话表。

    存储用户与 AI 助手的对话会话。
    """

    __tablename__ = "ai_conversations"

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 会话模式：trade_analysis / strategy / book_qa / general
    mode: Mapped[str] = mapped_column(String(50), nullable=False)

    # 会话标题
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 上下文信息（携带的会话上下文）
    context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class AIMessage(Base):
    """AI 消息表。

    存储会话中的每条消息（用户消息和 AI 回复）。
    """

    __tablename__ = "ai_messages"

    # 所属会话
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id"),
        index=True,
        nullable=False,
    )

    # 角色：user / assistant / system
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # 消息内容
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 使用的 token 数
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 用户反馈：none / like / dislike
    feedback: Mapped[str] = mapped_column(
        String(10), default="none", nullable=False
    )
