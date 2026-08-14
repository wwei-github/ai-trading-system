"""交易信号模型（Stage 8.3，对齐 PRD §5.8.2）。"""

import uuid
from typing import Any, Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Signal(Base):
    """交易信号表。

    存储策略生成的交易信号（规则引擎 + AI 引擎）。
    用户可标记：采纳 / 忽略 / 已执行。
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

    # 方向：buy / sell / hold
    side: Mapped[str] = mapped_column(String(10), nullable=False)

    # 信号强度（0.0 ~ 1.0）
    strength: Mapped[float] = mapped_column(Float, nullable=False)

    # 信号原因
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 信号来源：rule（规则引擎） / ai（AI 引擎）
    source: Mapped[str] = mapped_column(
        String(10), default="ai", nullable=False
    )

    # 信号状态：pending（待处理）/ adopted（已采纳）/ ignored（已忽略）/ executed（已执行）
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )

    # 附加上下文（指标数据、市场环境等）
    context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
