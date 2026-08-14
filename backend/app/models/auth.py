"""鉴权相关模型。

包含 RefreshToken / LoginDevice / EmailVerificationCode / PasswordResetCode 4 张表。
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RefreshToken(Base):
    """Refresh Token 表。

    每个 Refresh Token 一行，支持登出黑名单（is_revoked）。
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Token 哈希（SHA-256(token)），不存原文
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # 是否已撤销（登出 / 重设密码后撤销）
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 过期时间
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # 创建时设备/IP（用于审计）
    device_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class LoginDevice(Base):
    """登录设备记录表。

    用于"登录设备列表 + 强制下线"功能。
    """

    __tablename__ = "login_devices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # 设备名称（User-Agent 简化）
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # IP 地址
    ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 最后活跃时间
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # 是否已强制下线
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EmailVerificationCode(Base):
    """邮箱验证码表（注册验证）。

    一次一码，验证成功后失效。
    """

    __tablename__ = "email_verification_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # 验证码（6 位数字或 token）
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # 是否已使用
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 过期时间
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class PasswordResetCode(Base):
    """密码找回验证码表。"""

    __tablename__ = "password_reset_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
