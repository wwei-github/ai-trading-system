"""AI 回测主记录模型。"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AIBacktest(Base):
    """AI 回测主记录。"""

    __tablename__ = "ai_backtests"

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # kline_count / time_span
    kline_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_span_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_span_unit: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    initial_capital: Mapped[float] = mapped_column(
        Numeric(20, 2), nullable=False
    )
    fee_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.001)
    use_ai: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    total_klines: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_klines: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending / running / completed / failed

    result_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 关系
    strategy = relationship("Strategy", lazy="joined")
    trades = relationship(
        "AIBacktestTrade", back_populates="backtest",
        order_by="AIBacktestTrade.index",
        lazy="selectin",
        cascade="all, delete-orphan",
    )