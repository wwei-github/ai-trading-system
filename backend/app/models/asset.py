"""资产快照模型。"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AssetSnapshot(Base):
    """资产快照表。

    定期记录用户在各交易所的总资产和持仓明细。
    """

    __tablename__ = "asset_snapshots"

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

    # 总资产（USD 估值）
    total_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)

    # 各币种余额明细
    # {"BTC": {"free": 0.1, "used": 0, "total": 0.1, "usd": 5000}, ...}
    balances: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 快照时间
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
