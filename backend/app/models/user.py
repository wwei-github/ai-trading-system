"""用户模型。"""

from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """用户表。

    存储系统用户信息。本项目不包含登录/认证流程，
    该模型主要用于数据关联和审计。
    """

    __tablename__ = "users"

    # 邮箱
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    # 密码哈希（本项目不使用认证，保留字段以兼容架构）
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # 昵称
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)

    # 角色：admin / trader / viewer
    role: Mapped[str] = mapped_column(String(20), default="trader", nullable=False)

    # 是否激活
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # TOTP 密钥（二次验证，保留字段）
    totp_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
