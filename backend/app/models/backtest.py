"""回测模型。"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Backtest(Base):
    """回测记录表。

    存储策略回测的输入参数和结果。
    """

    __tablename__ = "backtests"

    # 关联策略
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strategies.id"),
        index=True,
        nullable=False,
    )

    # 回测交易对
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)

    # 时间周期：1m / 5m / 1h / 1d 等
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)

    # 回测开始日期
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 回测结束日期
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 初始资金（USD）
    initial_capital: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False
    )

    # 回测参数
    params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 回测结果：收益率、最大回撤、夏普比率等
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 状态：pending / running / completed / failed
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
