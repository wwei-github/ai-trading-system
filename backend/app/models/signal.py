"""交易信号模型。"""

import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Signal(Base):
    """交易信号表。

    存储策略生成的交易信号。
    """

    __tablename__ = "signals"

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 关联策略
    strategy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True
    )

    # 交易对
    symbol: Mapped[str] = mapped_column(String(30), index=True, nullable=False)

    # 方向：buy / sell
    side: Mapped[str] = mapped_column(String(10), nullable=False)

    # 信号强度（0.0 ~ 1.0）
    strength: Mapped[float] = mapped_column(Float, nullable=False)

    # 信号原因
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
