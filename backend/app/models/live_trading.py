"""实盘交易模型（Stage 6.7，对齐 PRD §5.6.5）。

LiveStrategyInstance: 实盘策略运行实例
LiveOrder: 实盘信号订单（半自动模式需用户确认）
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Float, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LiveStrategyInstance(Base):
    """实盘策略运行实例。

    记录策略实盘运行的配置、状态、风控参数。
    V1 默认半自动模式（信号推送后用户确认下单）。
    """

    __tablename__ = "live_strategy_instances"

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 关联策略
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), index=True, nullable=False
    )

    # 关联交易所账号
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exchange_accounts.id"), nullable=False
    )

    # 交易对
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)

    # 时间周期
    timeframe: Mapped[str] = mapped_column(String(10), default="1h", nullable=False)

    # 运行模式：semi_auto（半自动）/ full_auto（全自动，V2）
    mode: Mapped[str] = mapped_column(
        String(20), default="semi_auto", nullable=False
    )

    # 状态：running / paused / stopped
    status: Mapped[str] = mapped_column(
        String(20), default="running", nullable=False
    )

    # 风控参数（快照）
    risk_params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 策略参数（快照）
    strategy_params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 统计
    total_signals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_executed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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

    # 停止原因
    stop_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class LiveOrder(Base):
    """实盘信号订单（半自动模式需用户确认）。

    策略生成信号 → 写入 LiveOrder → 用户确认 → 执行下单。
    """

    __tablename__ = "live_orders"

    # 关联实盘实例
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_strategy_instances.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # 关联策略
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), index=True, nullable=False
    )

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 关联交易所账号
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exchange_accounts.id"), nullable=False
    )

    # 交易对
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)

    # 方向
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy / sell

    # 订单类型
    order_type: Mapped[str] = mapped_column(
        String(20), default="market", nullable=False
    )

    # 建议价格（信号生成时的价格）
    suggested_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 建议数量
    suggested_amount: Mapped[float] = mapped_column(Float, nullable=False)

    # 信号强度（1-5 星）
    signal_strength: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # 信号理由
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 状态：pending / confirmed / executed / rejected / expired / cancelled
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )

    # 信号生成时间
    signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # 用户确认时间
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 实际执行时间
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 交易所订单 ID（执行后回填）
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 实际成交价格
    executed_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 实际成交数量
    executed_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 过期时间（60s 未确认自动取消）
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 风控校验结果
    risk_check_passed: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, default=None
    )

    # 风控拒绝原因
    risk_reject_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 额外信息
    extra: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
