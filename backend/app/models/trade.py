"""交易记录模型。"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Trade(Base):
    """交易记录表。

    存储从交易所同步的交易历史。
    """

    __tablename__ = "trades"

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 所属交易所账号
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exchange_accounts.id"),
        index=True,
        nullable=False,
    )

    # 交易所名称
    exchange: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    # 交易对：BTC/USDT
    symbol: Mapped[str] = mapped_column(String(30), index=True, nullable=False)

    # 市场类型：spot / futures / margin
    market_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 方向：buy / sell
    side: Mapped[str] = mapped_column(String(10), nullable=False)

    # 订单类型：market / limit / stop 等
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 成交价格
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    # 成交数量
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)

    # 杠杆倍数（合约交易）
    leverage: Mapped[Optional[int]] = mapped_column(nullable=True)

    # 手续费
    fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)

    # 手续费币种
    fee_currency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # 订单状态：filled / partial / canceled
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    # 关联策略
    strategy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True
    )

    # 标签列表：["网格", "趋势"]
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 备注
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 交易所订单 ID
    exchange_order_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    # 来源：manual / exchange_sync / import / paper / live
    source: Mapped[str] = mapped_column(
        String(20), default="manual", nullable=False
    )

    # 成交时间
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
