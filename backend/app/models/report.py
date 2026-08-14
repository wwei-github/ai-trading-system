"""分析报告模型（Stage 8.4，对齐 PRD §5.8.3）。"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Report(Base):
    """分析报告表。

    存储系统自动生成或用户手动生成的交易分析报告。
    支持 3 种周期：daily / weekly / monthly。
    报告结构为 5 章：概述 / 指标分析 / 趋势分析 / 风险评估 / 改进建议。
    """

    __tablename__ = "reports"

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    # 报告类型：trade / strategy / portfolio
    report_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 报告周期：daily / weekly / monthly / custom
    period: Mapped[str] = mapped_column(
        String(20), default="custom", nullable=False
    )

    # 报告标题
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # 报告内容（Markdown 格式，5 章结构）
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 报告时间范围
    period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # AI 总结（自然语言摘要）
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 附加上下文数据
    context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
