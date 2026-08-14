"""AI 回测交易明细模型。"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AIBacktestTrade(Base):
    """AI 回测交易明细。"""

    __tablename__ = "ai_backtest_trades"

    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_backtests.id"), nullable=False, index=True
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # long / short

    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)

    open_ai_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    open_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    open_confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    stop_loss: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)

    exit_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_ai_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    holding_bars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    fee: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)

    extra: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    # 关系
    backtest = relationship("AIBacktest", back_populates="trades")