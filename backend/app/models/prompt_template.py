"""Prompt 模板模型。"""

from typing import Optional

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PromptTemplate(Base):
    """Prompt 模板表。

    存储 AI 回测各阶段使用的 Prompt 模板，支持按分类管理。
    """

    __tablename__ = "prompt_templates"

    # 模板分类：initial_analysis / backtest_precheck / deep_analysis
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="模板分类"
    )

    # 模板名称
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="模板名称"
    )

    # 模板内容
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="模板内容（支持 {} 占位符）"
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用"
    )

    # 版本号
    version: Mapped[int] = mapped_column(
        default=1, nullable=False, comment="版本号"
    )