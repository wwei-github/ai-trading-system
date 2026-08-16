"""策略模型。"""

import uuid
from typing import Any, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Strategy(Base):
    """策略表。

    存储用户定义或从书籍中提取的交易策略。
    """

    __tablename__ = "strategies"

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 策略名称
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 策略类别：trend / grid / arbitrage / mean_reversion 等
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    # 策略描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 策略规则（结构化 DSL，对齐 StrategyDSL）
    rules: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 策略参数
    params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 来源书籍
    source_book_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id"), nullable=True
    )

    # 状态：draft / active / archived
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )

    # 是否为内置模板策略
    is_template: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # 额外属性（用于辅助信息，如融合优化来源）
    extra: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, default=dict, comment="额外属性"
    )
