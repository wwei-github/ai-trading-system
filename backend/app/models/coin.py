"""币种行情数据模型。

Stage 5 新增：
- Kline：K 线历史数据表（symbol + timeframe + open_time 唯一）
- Watchlist：用户自选币种表（user_id + symbol 唯一）

注：暂未做 PostgreSQL 分区表，使用普通表 + 唯一索引 + 查询索引。
V1.2 数据量增大后可平滑迁移到分区表（按 symbol LIST + open_time RANGE）。
"""

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Kline(Base):
    """K 线历史数据表。

    存储从交易所抓取的 OHLCV 数据，按 (symbol, timeframe, open_time) 唯一去重。
    来源 source：ccxt / import / paper（模拟交易回放）。
    """

    __tablename__ = "klines"
    __table_args__ = (
        # 唯一约束：(symbol, timeframe, open_time) 去重
        UniqueConstraint(
            "symbol", "timeframe", "open_time", name="uq_klines_symbol_tf_opentime"
        ),
        # 查询索引：按 symbol + tf + 时间倒序（K 线列表常用）
        Index(
            "ix_klines_symbol_tf_time",
            "symbol",
            "timeframe",
            "open_time",
        ),
    )

    # 交易对（CCXT 风格，如 BTC/USDT）
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # 时间周期：1m/5m/15m/30m/1h/2h/4h/6h/12h/1d/3d/1w/1M
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # 开盘时间（UTC，毫秒级时间戳转为 datetime）
    open_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # OHLCV
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # 成交额（quote volume，USDT 计价；用于 VWAP 计算）
    quote_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 数据来源：ccxt / import / paper
    source: Mapped[str] = mapped_column(String(20), default="ccxt", nullable=False)

    # 交易所名称（多所合并去重时区分来源）
    exchange: Mapped[str] = mapped_column(String(30), default="binance", nullable=False)


class Watchlist(Base):
    """用户自选币种表。

    每用户最多 200 个自选（业务规则在 service 层校验）。
    """

    __tablename__ = "watchlist"
    __table_args__ = (
        # 每用户下币种唯一
        UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
        # 按用户 + 排序字段查询
        Index("ix_watchlist_user_sort", "user_id", "sort_order"),
    )

    # 所属用户
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # 交易对
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)

    # 备注（用户自定义，如"长期关注"）
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 排序权重（数字越小越靠前；默认 100）
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    # 添加价格（用于追踪自添加以来的涨跌幅）
    added_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
