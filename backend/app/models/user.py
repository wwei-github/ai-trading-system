"""用户模型。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """用户表。

    存储系统用户信息，包含 JWT 鉴权所需字段。
    """

    __tablename__ = "users"

    # 邮箱
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    # 密码哈希（bcrypt）
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # 昵称
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)

    # 角色：admin / trader / viewer
    role: Mapped[str] = mapped_column(String(20), default="trader", nullable=False)

    # 是否激活
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # TOTP 密钥（2FA 启用后加密存储）
    totp_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 是否已启用 2FA
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 邮箱是否已验证
    email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # 连续登录失败次数（用于锁定判定）
    failed_login_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    # 锁定截止时间（NULL=未锁定）
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 最后登录时间
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 最后登录 IP
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 风险提示同意时间（首次登录必须勾选）
    risk_agreed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

