"""审计日志模型。"""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """审计日志表。

    记录用户的关键操作，用于安全审计和行为追踪。
    """

    __tablename__ = "audit_logs"

    # 操作用户
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # 操作动作：create / update / delete / sync 等
    action: Mapped[str] = mapped_column(String(50), nullable=False)

    # 资源类型：account / trade / strategy 等
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 资源 ID
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 操作详情
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 操作 IP 地址
    ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
