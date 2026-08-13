"""币种分析接口。"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.coin_service import CoinService

router = APIRouter(prefix="/coins", tags=["币种分析"])

_service = CoinService()


@router.get("/health", summary="健康检查")
async def health_check():
    """币种分析模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "coins"})


@router.get("", summary="获取热门币种列表")
async def list_top_coins(
    limit: int = Query(10, ge=1, le=50, description="数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取热门币种列表（按 24h 成交额排序）。"""
    coins = await _service.get_top_coins(limit=limit)
    return ApiResponse(data=[c.model_dump() for c in coins])


@router.get("/compare", summary="多币种对比")
async def compare_coins(
    symbols: str = Query(..., description="交易对列表，逗号分隔，如 BTC/USDT,ETH/USDT"),
    timeframe: str = Query("1d", description="时间周期"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """多币种对比分析。"""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    results = await _service.compare_coins(symbol_list, timeframe)
    return ApiResponse(data=results)


@router.get("/{symbol}", summary="获取币种基本信息")
async def get_coin_info(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取币种基本信息（含实时行情）。"""
    info = await _service.get_coin_info(symbol)
    return ApiResponse(data=info.model_dump() if info else None)


@router.get("/{symbol}/ticker", summary="获取实时行情")
async def get_ticker(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取币种实时行情。"""
    info = await _service.get_coin_info(symbol)
    return ApiResponse(data=info.model_dump() if info else None)


@router.get("/{symbol}/kline", summary="获取 K 线数据")
async def get_kline(
    symbol: str,
    timeframe: str = Query("1d", description="时间周期：1m/5m/1h/1d"),
    limit: int = Query(100, ge=1, le=1000, description="K 线数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 K 线数据。"""
    kline = await _service.get_kline_data(symbol, timeframe, limit)
    return ApiResponse(data=kline)


@router.get("/{symbol}/indicators", summary="获取技术指标")
async def get_indicators(
    symbol: str,
    timeframe: str = Query("1d", description="时间周期"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取技术指标（RSI/MACD/MA/布林带等）。"""
    analysis = await _service.get_coin_analysis(symbol, timeframe)
    return ApiResponse(data=analysis.model_dump() if analysis else None)
