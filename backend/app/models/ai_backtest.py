"""AI 回测主记录模型。"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AIBacktest(Base):
    """AI 回测主记录。"""

    __tablename__ = "ai_backtests"

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # kline_count / time_span
    kline_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_span_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_span_unit: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    initial_capital: Mapped[float] = mapped_column(
        Numeric(20, 2), nullable=False
    )
    fee_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.001)
    use_ai: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    total_klines: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_klines: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending / running / completed / failed / cancelling / cancelled

    result_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ========== 08-AI回测K线分析优化 新增字段 ==========

    # 多策略融合
    parent_backtest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_backtests.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="父回测 ID（多策略融合时使用）"
    )
    strategy_ids: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, comment="参与回测的策略 ID 列表"
    )

    # 两级 AI 过滤统计
    ai_call_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0, comment="AI 调用总次数"
    )
    precheck_total: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0, comment="快速预筛总次数"
    )
    precheck_triggered: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0, comment="预筛触发 AI 分析次数"
    )

    # 本地模型预筛配置
    use_local_model: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="使用本地模型进行预筛"
    )
    local_model_klines: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, comment="本地模型分析的 K 线数量"
    )

    # 预筛开关
    use_precheck: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用预筛（关闭后每根 K 线都直接深度分析）"
    )

    # 初始化 300 根预热分析
    initial_analysis: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, comment="初始化 AI 分析结果（趋势、关键位、摘要）"
    )

    # 深度分析日志
    ai_analysis_logs: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, default=list, comment="深度分析日志列表（复盘用）"
    )

    # Prompt 模板 ID 映射
    prompt_template_ids: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, default=dict,
        comment="使用的 Prompt 模板 ID 映射 {category: template_id}"
    )

    # 关系
    strategy = relationship("Strategy", lazy="joined")
    trades = relationship(
        "AIBacktestTrade", back_populates="backtest",
        order_by="AIBacktestTrade.index",
        lazy="selectin",
        cascade="all, delete-orphan",
    )