"""币种分析接口（Stage 5 完整实现，对齐 PRD §5.5）。

端点清单：
- GET  /coins/health                  健康检查
- GET  /coins                         Top100 行情列表（搜索 + 排序）
- GET  /coins/watchlist               用户自选列表（含实时行情）
- POST /coins/watchlist               添加自选
- PATCH /coins/watchlist/{symbol}     更新自选（note / sort_order）
- DELETE /coins/watchlist/{symbol}    移除自选
- GET  /coins/compare                 多币种对比（归一化收益 + 相关性矩阵）
- GET  /coins/{symbol}                [兼容] 币种基本信息
- GET  /coins/{symbol}/ticker         实时行情
- GET  /coins/{symbol}/kline          K 线（DB 优先 + CCXT 补齐）
- GET  /coins/{symbol}/indicators     14 类技术指标
- GET  /coins/{symbol}/analysis       AI 分析报告（6 部分，V1 纯规则）
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.coin import (
    WatchlistCreate,
    WatchlistUpdate,
)
from app.schemas.common import ApiResponse
from app.services.coin_service import CoinService

router = APIRouter(prefix="/coins", tags=["币种分析"])


# ---------- 健康检查 ----------

@router.get("/health", summary="健康检查")
async def health_check():
    """币种分析模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "coins"})


# ==================== Top100 行情列表 ====================

@router.get("", summary="Top100 行情列表")
async def list_top_coins(
    limit: int = Query(100, ge=1, le=200, description="返回数量"),
    search: Optional[str] = Query(None, description="按名称/代码搜索（如 BTC）"),
    sort_by: str = Query(
        "volume_24h",
        description="排序字段：volume_24h / price_change_24h / current_price",
    ),
    sort_order: str = Query("desc", description="asc / desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Top100 币种行情（按 24h 成交额排序，Redis 30s 缓存）。

    数据源：Binance 现货市场 /USDT 交易对。
    """
    service = CoinService(db)
    coins = await service.get_top_coins(
        limit=limit, search=search, sort_by=sort_by, sort_order=sort_order
    )
    return ApiResponse(data=[c.model_dump(mode="json") for c in coins])


# ==================== Watchlist（用户自选） ====================

@router.get("/watchlist", summary="用户自选列表")
async def list_watchlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户自选币种列表（含实时行情 + 自添加以来涨跌幅）。"""
    service = CoinService(db)
    items = await service.list_watchlist(current_user.id)
    return ApiResponse(data=[i.model_dump(mode="json") for i in items])


@router.post("/watchlist", summary="添加自选")
async def add_to_watchlist(
    payload: WatchlistCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加币种到自选列表（每用户最多 200，PRD §5.5.1 R3）。"""
    service = CoinService(db)
    item = await service.add_to_watchlist(current_user.id, payload)
    return ApiResponse(data=item.model_dump(mode="json"))


@router.patch("/watchlist/{symbol}", summary="更新自选")
async def update_watchlist(
    symbol: str = Path(..., description="交易对，路径中用 BTC-USDT 或 BTCUSDT（自动转 BTC/USDT）"),
    payload: WatchlistUpdate = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新自选项（note / sort_order）。"""
    service = CoinService(db)
    symbol = service._normalize_symbol(symbol)
    item = await service.update_watchlist(current_user.id, symbol, payload or WatchlistUpdate())
    return ApiResponse(data=item.model_dump(mode="json"))


@router.delete("/watchlist/{symbol}", summary="移除自选")
async def remove_from_watchlist(
    symbol: str = Path(..., description="交易对，路径中用 BTC-USDT 或 BTCUSDT（自动转 BTC/USDT）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从自选列表移除指定币种。"""
    service = CoinService(db)
    symbol = service._normalize_symbol(symbol)
    ok = await service.remove_from_watchlist(current_user.id, symbol)
    return ApiResponse(data={"removed": ok, "symbol": symbol})


# ==================== 多币种对比 ====================

@router.get("/compare", summary="多币种对比")
async def compare_coins(
    symbols: str = Query(
        ...,
        description="交易对列表，逗号分隔，如 BTC/USDT,ETH/USDT（2-8 个）",
    ),
    timeframe: str = Query("1d", description="K 线周期"),
    days: int = Query(30, ge=7, le=365, description="对比天数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """多币种对比（归一化收益曲线 + N×N 相关性矩阵）。

    PRD §5.5.3：
    - 最多 8 个币种
    - 归一化收益曲线（首日为 0%）
    - 相关性矩阵（近 N 日收益率 Pearson 系数）
    """
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    service = CoinService(db)
    resp = await service.compare_coins(symbol_list, timeframe, days)
    return ApiResponse(data=resp.model_dump(mode="json"))


# ==================== 单币种详情 / 行情 / K 线 / 指标 / 分析 ====================

@router.get("/{symbol}", summary="[兼容] 获取币种基本信息")
async def get_coin_info(
    symbol: str = Path(..., description="交易对，路径中用 BTC-USDT 或 BTCUSDT（自动转 BTC/USDT）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """[兼容] 获取币种基本信息（含实时行情）。"""
    service = CoinService(db)
    symbol = service._normalize_symbol(symbol)
    info = await service.get_coin_info(symbol)
    return ApiResponse(data=info.model_dump(mode="json") if info else None)


@router.get("/{symbol}/ticker", summary="实时行情")
async def get_ticker(
    symbol: str = Path(..., description="交易对，路径中用 BTC-USDT 或 BTCUSDT（自动转 BTC/USDT）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取币种实时行情（Redis 15s 缓存）。

    返回字段：symbol / name / current_price / price_change_24h / volume_24h / timestamp
    """
    service = CoinService(db)
    symbol = service._normalize_symbol(symbol)
    info = await service.get_ticker(symbol)
    return ApiResponse(data=info.model_dump(mode="json"))


@router.get("/{symbol}/kline", summary="K 线数据")
async def get_kline(
    symbol: str = Path(..., description="交易对，路径中用 BTC-USDT 或 BTCUSDT（自动转 BTC/USDT）"),
    timeframe: str = Query(
        "1d",
        description="时间周期：1m/5m/15m/30m/1h/2h/4h/6h/12h/1d/3d/1w/1M",
    ),
    limit: int = Query(200, ge=1, le=1000, description="K 线数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 K 线数据（OHLCV）。

    策略：
    1. 优先读 DB（klines 表，按 open_time 降序取 limit 根）
    2. 若不足或最新一根已过期（超过 2 个周期），从 CCXT 补齐并入库
    3. 返回数据按时间正序排列（前端 K 线图需要）

    响应字段：symbol / timeframe / data[] / source(ccxt/db/ccxt+db) / last_updated
    """
    service = CoinService(db)
    symbol = service._normalize_symbol(symbol)
    resp = await service.get_klines(symbol, timeframe, limit)
    return ApiResponse(data=resp.model_dump(mode="json"))


@router.get("/{symbol}/indicators", summary="14 类技术指标")
async def get_indicators(
    symbol: str = Path(..., description="交易对，路径中用 BTC-USDT 或 BTCUSDT（自动转 BTC/USDT）"),
    timeframe: str = Query("1d", description="时间周期"),
    types: Optional[str] = Query(
        None,
        description="指标类型，逗号分隔；不传则全部。"
        "可选：ma,ema,macd,boll,dmi,rsi,kdj,cci,willr,obv,vwap,atr,stdch",
    ),
    limit: int = Query(200, ge=50, le=1000, description="K 线数量（用于计算指标）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """计算 14 类技术指标（基于 K 线数据）。

    指标清单（PRD §5.5.2）：
    - 均线：MA（5/10/20/60/120/200）、EMA
    - 趋势：MACD、BOLL、DMI
    - 震荡：RSI、KDJ、CCI、Williams %R
    - 成交量：OBV、VWAP
    - 波动：ATR、标准差通道（STDCH）

    返回各指标最新值；数据不足时对应字段为 null。
    """
    indicator_types = (
        [t.strip() for t in types.split(",") if t.strip()] if types else None
    )
    service = CoinService(db)
    symbol = service._normalize_symbol(symbol)
    resp = await service.get_indicators(symbol, timeframe, indicator_types, limit)
    return ApiResponse(data=resp.model_dump(mode="json"))


@router.get("/{symbol}/analysis", summary="AI 分析报告")
async def get_analysis(
    symbol: str = Path(..., description="交易对，路径中用 BTC-USDT 或 BTCUSDT（自动转 BTC/USDT）"),
    timeframe: str = Query("1d", description="时间周期"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成 AI 分析报告（6 部分结构，V1 纯规则）。

    报告结构（PRD §5.5.4）：
    1. trend：趋势判断（短中长期 MA 多空）
    2. support_resistance：支撑阻力（近期高低 + Fibonacci 0.382/0.5/0.618）
    3. indicator_signals：指标信号汇总（MA/RSI/MACD/BOLL）
    4. volume_price：量价特征
    5. risk：风险提示（ATR/波动率 z-score）
    6. recommendation：操作建议（观察/轻仓尝试/不推荐 3 档，含免责声明）

    V1 为纯规则实现，V1.3 将升级为 LLM 版本。
    """
    service = CoinService(db)
    symbol = service._normalize_symbol(symbol)
    report = await service.analyze_coin(symbol, timeframe)
    return ApiResponse(data=report.model_dump(mode="json"))
