"""回测交易明细模型（Stage 6.3）。

存储每次回测的开平仓配对记录，用于回测报告明细表展示。
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BacktestTrade(Base):
    """回测交易明细表。

    每条记录表示一次完整的开平仓配对。
    """

    __tablename__ = "backtest_trades"

    # 关联回测
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # 关联策略（冗余，便于查询）
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strategies.id"),
        index=True,
        nullable=False,
    )

    # 交易方向
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # long / short

    # 开仓信息
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)

    # 平仓信息
    exit_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 盈亏
    pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 持仓周期数
    holding_bars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 平仓原因：signal / stop_loss / take_profit / time_stop / trailing_stop / end_of_data
    exit_reason: Mapped[str] = mapped_column(
        String(20), default="signal", nullable=False
    )

    # 交易对
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)

    # 额外信息（如手续费、滑点）
    extra: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
