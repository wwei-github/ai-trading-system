"""交易所账号模型。"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExchangeAccount(Base):
    """交易所账号表。

    存储用户绑定的交易所 API 凭证，敏感字段使用 AES-256 加密存储。
    """

    __tablename__ = "exchange_accounts"

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 交易所名称：binance / okx / bybit 等
    exchange: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    # 账号标签（用户自定义名称）
    label: Mapped[str] = mapped_column(String(100), nullable=False)

    # API Key（加密存储）
    api_key_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)

    # API Secret（加密存储）
    api_secret_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)

    # 口令（加密存储，OKX 等交易所需要）
    passphrase_encrypted: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )

    # 权限列表：["spot", "futures", "withdraw"]
    permissions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 是否为测试网
    is_testnet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 状态：active / disabled / abnormal / expired
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )

    # 是否启用（同步任务和策略只读取 enabled=true 的账号）
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # 最后同步时间
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
