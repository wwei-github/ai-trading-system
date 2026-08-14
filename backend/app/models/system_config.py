"""系统配置模型（Stage 8.5，对齐 PRD §5.9.1）。

以 K/V 表形式存储可持久化的系统配置，
支持 5 类：ai / exchanges / risk / notifications / storage。
"""

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SystemConfig(Base):
    """系统配置表。

    以 category + key 的形式存储配置项，value 为 JSONB。
    Admin 可通过 API 读写；应用启动时加载到内存缓存。
    """

    __tablename__ = "system_configs"

    # 配置分类：ai / exchanges / risk / notifications / storage
    category: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )

    # 配置键（分类内唯一）
    key: Mapped[str] = mapped_column(String(100), nullable=False)

    # 配置值（JSONB，支持复杂结构）
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # 配置描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
