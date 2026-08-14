"""交易标签模型。"""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TradeTag(Base):
    """交易标签表。

    每用户独立维护标签库（user_id + name 唯一），
    支持颜色和合并操作。
    """

    __tablename__ = "trade_tags"
    __table_args__ = (
        # 每用户下标签名唯一
        UniqueConstraint("user_id", "name", name="uq_trade_tags_user_name"),
    )

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 标签名
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # 颜色（HEX，如 #1890ff）
    color: Mapped[str] = mapped_column(
        String(20), default="#1890ff", nullable=False
    )

    # 使用次数（冗余字段，加速标签列表渲染）
    usage_count: Mapped[int] = mapped_column(default=0, nullable=False)
