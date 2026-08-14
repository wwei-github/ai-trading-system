"""交易记录 Schema。

字段口径对齐 PRD §6.3，共 20 字段：
exchange / symbol / market_type / side / order_type / price / quantity /
leverage / fee / fee_currency / status / strategy_id / tags / note /
exchange_order_id / source / executed_at + 盈亏计算列（pnl / pnl_ratio /
matched_trade_id / holding_seconds）。
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------- 枚举校验 ----------

VALID_SIDES = {"buy", "sell"}
VALID_MARKET_TYPES = {"spot", "futures", "margin"}
VALID_ORDER_TYPES = {"market", "limit", "stop", "stop_limit", "post_only", "ioc", "fok"}
VALID_STATUS = {"filled", "partial", "canceled", "open"}
VALID_SOURCES = {"manual", "exchange_sync", "import", "paper", "live"}


# ---------- 交易记录 ----------

class TradeBase(BaseModel):
    """交易基础字段（创建/更新共用）。"""

    exchange: str = Field(..., max_length=50, description="交易所名称")
    symbol: str = Field(..., max_length=30, description="交易对，如 BTC/USDT")
    market_type: str = Field("spot", description="市场类型：spot/futures/margin")
    side: str = Field(..., description="方向：buy/sell")
    order_type: str = Field("market", description="订单类型")
    price: Decimal = Field(..., gt=0, description="成交价格")
    quantity: Decimal = Field(..., gt=0, description="成交数量")
    leverage: Optional[int] = Field(None, ge=1, le=125, description="杠杆倍数（合约）")
    fee: Optional[Decimal] = Field(None, ge=0, description="手续费")
    fee_currency: Optional[str] = Field(None, max_length=20, description="手续费币种")
    status: str = Field("filled", description="订单状态")
    strategy_id: Optional[uuid.UUID] = Field(None, description="关联策略 ID")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    note: Optional[str] = Field(None, max_length=500, description="备注")
    exchange_order_id: Optional[str] = Field(None, max_length=100, description="交易所订单 ID")
    executed_at: datetime = Field(..., description="成交时间")

    @field_validator("side")
    @classmethod
    def validate_side(cls, v: str) -> str:
        if v not in VALID_SIDES:
            raise ValueError(f"side 必须为 {VALID_SIDES} 之一")
        return v

    @field_validator("market_type")
    @classmethod
    def validate_market_type(cls, v: str) -> str:
        if v not in VALID_MARKET_TYPES:
            raise ValueError(f"market_type 必须为 {VALID_MARKET_TYPES} 之一")
        return v

    @field_validator("order_type")
    @classmethod
    def validate_order_type(cls, v: str) -> str:
        if v not in VALID_ORDER_TYPES:
            raise ValueError(f"order_type 必须为 {VALID_ORDER_TYPES} 之一")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUS:
            raise ValueError(f"status 必须为 {VALID_STATUS} 之一")
        return v


class TradeCreate(TradeBase):
    """手动创建交易记录。"""

    account_id: uuid.UUID = Field(..., description="所属交易所账号 ID")
    # source 由后端固定为 manual，不接受前端传入


class TradeUpdate(BaseModel):
    """更新交易记录。

    来源为 exchange_sync 的交易仅允许更新 tags / note（只读保护）。
    """

    tags: Optional[List[str]] = None
    note: Optional[str] = Field(None, max_length=500)
    strategy_id: Optional[uuid.UUID] = None
    # 以下字段仅 source=manual/import/paper/live 可修改
    exchange: Optional[str] = None
    symbol: Optional[str] = None
    market_type: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    price: Optional[Decimal] = None
    quantity: Optional[Decimal] = None
    leverage: Optional[int] = None
    fee: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    status: Optional[str] = None
    executed_at: Optional[datetime] = None


class TradeResponse(BaseModel):
    """交易记录响应（含盈亏字段）。"""

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    exchange: str
    symbol: str
    market_type: str
    side: str
    order_type: str
    price: Decimal
    quantity: Decimal
    leverage: Optional[int] = None
    fee: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    status: str
    strategy_id: Optional[uuid.UUID] = None
    tags: Optional[List[str]] = None
    note: Optional[str] = None
    exchange_order_id: Optional[str] = None
    source: str
    # 盈亏字段
    pnl: Optional[Decimal] = None
    pnl_ratio: Optional[Decimal] = None
    matched_trade_id: Optional[uuid.UUID] = None
    holding_seconds: Optional[int] = None
    executed_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------- 查询参数 ----------

class TradeQueryParams(BaseModel):
    """交易记录多维筛选参数。

    支持的筛选维度（对齐 PRD §5.3.1 R3）：
    时间范围 / 交易对 / 账号 / 策略 / 标签 / 方向 / 盈亏状态 / 交易所
    + 全文搜索（symbol/note）+ 分页。
    """

    exchange: Optional[str] = None
    symbol: Optional[str] = None
    account_id: Optional[uuid.UUID] = None
    strategy_id: Optional[uuid.UUID] = None
    side: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    # 标签筛选（数组 @> 操作）
    tags: Optional[List[str]] = None
    # 盈亏状态：profit / loss / breakeven / unrealized
    pnl_status: Optional[str] = None
    # 全文搜索（symbol / note）
    search: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    # 排序字段
    sort_by: str = Field("executed_at", description="排序字段")
    sort_order: str = Field("desc", description="asc / desc")


# ---------- 标签更新 ----------

class TradeTagUpdate(BaseModel):
    """交易标签/备注更新（exchange_sync 来源也允许）。"""

    tags: Optional[List[str]] = None
    note: Optional[str] = Field(None, max_length=500)


# ---------- 导入 ----------

class TradeImportItem(BaseModel):
    """批量导入的单条交易记录。"""

    exchange: str
    symbol: str
    market_type: str = "spot"
    side: str
    order_type: str = "market"
    price: Decimal
    quantity: Decimal
    leverage: Optional[int] = None
    fee: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    status: str = "filled"
    strategy_id: Optional[uuid.UUID] = None
    tags: Optional[List[str]] = None
    note: Optional[str] = None
    exchange_order_id: Optional[str] = None
    executed_at: datetime


class TradeImportRequest(BaseModel):
    """批量导入交易记录请求。"""

    account_id: uuid.UUID
    trades: List[TradeImportItem]


class TradeImportResponse(BaseModel):
    """批量导入交易记录响应。"""

    total: int
    imported: int
    skipped: int
    errors: List[str] = Field(default_factory=list)


class TradeImportPreviewRow(BaseModel):
    """导入预览的单行结果。"""

    row_index: int
    valid: bool
    data: Optional[TradeImportItem] = None
    error: Optional[str] = None
    duplicate: bool = False


class TradeImportPreviewResponse(BaseModel):
    """导入预览响应。"""

    total: int
    valid: int
    invalid: int
    duplicates: int
    rows: List[TradeImportPreviewRow]


# ---------- 盈亏重算 ----------

class TradeRecalcRequest(BaseModel):
    """盈亏重算请求。"""

    trade_ids: Optional[List[uuid.UUID]] = Field(
        None, description="指定 trade ID 列表；为空则按 period 重算全部"
    )
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    symbol: Optional[str] = None


class TradeRecalcResponse(BaseModel):
    """盈亏重算响应。"""

    recalculated: int
    matched_pairs: int
    errors: List[str] = Field(default_factory=list)
