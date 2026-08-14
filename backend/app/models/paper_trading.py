"""模拟交易模型（Stage 6.6，对齐 PRD §5.6.4）。

PaperAccount: 虚拟账号（每策略+每币种一个）
PaperTrade: 虚拟交易记录（不与真实交易混表）
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Float
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PaperAccount(Base):
    """模拟交易虚拟账号。

    每次启动模拟交易创建一个虚拟账号，记录初始资金、当前权益、持仓状态。
    """

    __tablename__ = "paper_accounts"

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 关联策略
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), index=True, nullable=False
    )

    # 交易对
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)

    # 时间周期
    timeframe: Mapped[str] = mapped_column(String(10), default="1h", nullable=False)

    # 初始虚拟资金（USDT）
    initial_capital: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False
    )

    # 当前权益（USDT）
    current_equity: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False
    )

    # 可用资金
    available_cash: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False
    )

    # 当前持仓数量（正数=多头，负数=空头，0=空仓）
    position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 持仓均价
    avg_entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 状态：running / paused / stopped / terminated
    status: Mapped[str] = mapped_column(
        String(20), default="running", nullable=False
    )

    # 策略参数（快照，启动时的参数）
    strategy_params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 统计
    total_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=0, nullable=False
    )

    # 启动/停止时间
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PaperTrade(Base):
    """模拟交易记录（不与真实交易混合，PRD §5.6.4 R4）。"""

    __tablename__ = "paper_trades"

    # 关联虚拟账号
    paper_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("paper_accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # 关联策略（冗余）
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), index=True, nullable=False
    )

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 交易对
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)

    # 方向
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy / sell

    # 订单类型
    order_type: Mapped[str] = mapped_column(
        String(20), default="market", nullable=False
    )

    # 成交信息
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 成交时间
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # 信号来源（策略规则触发的具体条件）
    signal_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 平仓盈亏（仅平仓时有值）
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 额外信息
    extra: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
