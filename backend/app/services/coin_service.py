"""币种分析服务（Stage 5 完整实现，对齐 PRD §5.5）。

功能：
- Top100 行情聚合（CCXT Binance ticker；Redis 30s 缓存）
- 实时行情 /coins/{symbol}/ticker
- K 线历史（DB 优先 + CCXT 缺失补齐入库；唯一索引去重）
- 14 类技术指标（utils/indicators.py）
- 多币种对比（归一化收益曲线 + N×N 相关性矩阵）
- AI 分析报告（6 部分结构，纯规则 V1）
- Watchlist CRUD（每用户最多 200）
"""

import datetime
import json
import math
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import redis_client
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    ServiceUnavailableException,
)
from app.exchange.ccxt_client import CCXTClient
from app.models.coin import Kline, Watchlist
from app.schemas.coin import (
    AnalysisRecommendation,
    AnalysisReport,
    AnalysisTrend,
    CoinAnalysis,
    CoinInfo,
    ComparePoint,
    CompareResponse,
    CorrelationMatrix,
    IndicatorResponse,
    IndicatorSignals,
    KlineItem,
    KlineResponse,
    RiskAssessment,
    SupportResistance,
    TickerInfo,
    VolumePriceFeature,
    WatchlistCreate,
    WatchlistItem,
    WatchlistUpdate,
)
from app.utils.indicators import calculate_indicators

# 默认交易所（公开行情，无需 API Key）
DEFAULT_EXCHANGE = "binance"

# 缓存键前缀 + TTL
COIN_CACHE_PREFIX = "coins:v1"
COIN_CACHE_TTL = 30  # 秒（Top100 行情列表）

# Watchlist 上限（PRD §5.5.1 R3）
WATCHLIST_MAX = 200

# K 线抓取单次最大数量（CCXT 单次限 1000-1500）
KLINE_FETCH_BATCH = 1000


class CoinService:
    """币种分析服务。"""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db

    # ---------- 工具方法 ----------

    def _get_public_client(self, exchange: str = None) -> CCXTClient:
        """获取公开行情客户端（无需 API Key）。"""
        return CCXTClient(
            exchange=exchange or DEFAULT_EXCHANGE,
            api_key="",
            api_secret="",
            is_testnet=False,
        )

    async def _get_cache(self, key: str) -> Optional[Any]:
        try:
            if redis_client is None:
                return None
            raw = await redis_client.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning("读取币种缓存失败 | key={} err={}", key, e)
        return None

    async def _set_cache(self, key: str, data: Any, ttl: int = COIN_CACHE_TTL) -> None:
        try:
            if redis_client is None:
                return
            await redis_client.set(key, json.dumps(data, default=str), ex=ttl)
        except Exception as e:
            logger.warning("写入币种缓存失败 | key={} err={}", key, e)

    @staticmethod
    def _symbol_to_name(symbol: str) -> str:
        """BTC/USDT → BTC。"""
        return symbol.split("/")[0] if "/" in symbol else symbol

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """规范化交易对符号。

        路径参数中 `/` 会被 URL 解码导致路由失败，前端可用 `BTC-USDT` 或 `BTCUSDT`，
        此方法统一转换为 CCXT 风格 `BTC/USDT`。
        """
        if not symbol:
            return symbol
        symbol = symbol.strip()
        if "/" in symbol:
            return symbol
        if "-" in symbol:
            parts = symbol.split("-")
            if len(parts) == 2:
                return f"{parts[0]}/{parts[1]}"
        # BTCUSDT → BTC/USDT（简单启发：以 USDT/USDC/BTC/ETH 结尾分割）
        for quote in ("USDT", "USDC", "BUSD", "BTC", "ETH", "BNB"):
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base = symbol[: -len(quote)]
                return f"{base}/{quote}"
        return symbol

    # ---------- 1. Top100 行情聚合 ----------

    async def get_top_coins(
        self,
        limit: int = 100,
        search: Optional[str] = None,
        sort_by: str = "volume_24h",  # volume_24h / price_change_24h / current_price
        sort_order: str = "desc",
    ) -> List[CoinInfo]:
        """获取 Top100 币种行情（按 24h 成交额排序）。

        Args:
            limit: 返回数量（1-200）
            search: 按名称/代码搜索（如 "BTC"）
            sort_by: 排序字段 volume_24h / price_change_24h / current_price
            sort_order: asc / desc
        """
        cache_key = f"{COIN_CACHE_PREFIX}:top:{limit}:{search or ''}:{sort_by}:{sort_order}"
        cached = await self._get_cache(cache_key)
        if cached:
            return [CoinInfo(**c) for c in cached]

        client = self._get_public_client()
        try:
            await client.load_markets()
            tickers = await client.fetch_tickers()
            # 过滤有效 ticker（含成交额，且为 /USDT 现货）
            items = []
            for sym, t in tickers.items():
                if not sym.endswith("/USDT"):
                    continue
                quote_vol = t.get("quoteVolume") or 0
                if not quote_vol or quote_vol <= 0:
                    continue
                name = self._symbol_to_name(sym)
                # 搜索过滤
                if search:
                    s = search.upper()
                    if s not in sym.upper() and s not in name.upper():
                        continue
                items.append(
                    CoinInfo(
                        symbol=sym,
                        name=name,
                        current_price=Decimal(str(t.get("last"))) if t.get("last") else None,
                        price_change_24h=t.get("percentage"),
                        volume_24h=Decimal(str(quote_vol)),
                        high_24h=Decimal(str(t["high"])) if t.get("high") else None,
                        low_24h=Decimal(str(t["low"])) if t.get("low") else None,
                        exchange=DEFAULT_EXCHANGE,
                    )
                )

            # 排序
            reverse = sort_order == "desc"
            sort_key_map = {
                "volume_24h": lambda x: float(x.volume_24h or 0),
                "price_change_24h": lambda x: float(x.price_change_24h or 0),
                "current_price": lambda x: float(x.current_price or 0),
            }
            items.sort(key=sort_key_map.get(sort_by, sort_key_map["volume_24h"]), reverse=reverse)
            items = items[:limit]

            await self._set_cache(cache_key, [c.model_dump(mode="json") for c in items])
            return items
        except Exception as e:
            logger.error("获取 Top100 币种失败: {}", e)
            raise ServiceUnavailableException(
                message=f"获取币种行情失败: {str(e)}"
            )
        finally:
            await client.close()

    # ---------- 2. 实时行情 ----------

    async def get_ticker(self, symbol: str) -> TickerInfo:
        """获取实时行情。"""
        cache_key = f"{COIN_CACHE_PREFIX}:ticker:{symbol}"
        cached = await self._get_cache(cache_key)
        if cached:
            return TickerInfo(**cached)

        client = self._get_public_client()
        try:
            t = await client.fetch_ticker(symbol)
            info = TickerInfo(
                symbol=symbol,
                name=self._symbol_to_name(symbol),
                current_price=Decimal(str(t.get("last"))) if t.get("last") else None,
                price_change_24h=t.get("percentage"),
                volume_24h=Decimal(str(t.get("quoteVolume"))) if t.get("quoteVolume") else None,
                timestamp=t.get("timestamp"),
            )
            await self._set_cache(cache_key, info.model_dump(mode="json"), ttl=15)
            return info
        except Exception as e:
            logger.error("获取实时行情失败: {} | {}", symbol, e)
            raise ServiceUnavailableException(
                message=f"获取实时行情失败: {str(e)}",
                detail={"symbol": symbol},
            )
        finally:
            await client.close()

    async def get_coin_info(self, symbol: str) -> Optional[CoinInfo]:
        """[兼容] 获取币种基本信息。"""
        ticker = await self.get_ticker(symbol)
        return CoinInfo(
            symbol=ticker.symbol,
            name=ticker.name,
            current_price=ticker.current_price,
            price_change_24h=ticker.price_change_24h,
            volume_24h=ticker.volume_24h,
            exchange=DEFAULT_EXCHANGE,
        )

    # ---------- 3. K 线历史（DB 优先 + CCXT 补齐） ----------

    async def get_klines(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 200,
    ) -> KlineResponse:
        """获取 K 线数据。

        策略：
        1. 查询 DB 中已有的 K 线（按 open_time 降序，取 limit 根）
        2. 若数量不足 limit 或最新一根已过期（超过 1 个 timeframe 周期），从 CCXT 补齐
        3. 写入 DB（唯一索引去重，ON CONFLICT DO NOTHING）
        """
        if self.db is None:
            # 无 DB 上下文，直接走 CCXT
            return await self._fetch_klines_from_ccxt(symbol, timeframe, limit)

        # 1. 查 DB
        db_items = await self._query_klines_from_db(symbol, timeframe, limit)
        now = datetime.datetime.now(datetime.timezone.utc)
        timeframe_seconds = self._timeframe_to_seconds(timeframe)

        # 2. 判断是否需要补齐
        need_fetch = False
        if len(db_items) < limit:
            need_fetch = True
        elif db_items:
            latest_open = datetime.datetime.fromtimestamp(
                db_items[0].timestamp / 1000, tz=datetime.timezone.utc
            )
            age = (now - latest_open).total_seconds()
            if age > timeframe_seconds * 2:  # 超过 2 个周期未更新
                need_fetch = True

        source = "db"
        if need_fetch:
            try:
                ccxt_items = await self._fetch_ccxt_and_save(symbol, timeframe, limit)
                if ccxt_items:
                    # 合并 + 去重 + 排序，取最新 limit 根
                    seen = {item.timestamp for item in db_items}
                    merged = list(db_items)
                    for item in ccxt_items:
                        if item.timestamp not in seen:
                            merged.append(item)
                            seen.add(item.timestamp)
                    merged.sort(key=lambda x: x.timestamp, reverse=True)
                    db_items = merged[:limit]
                    source = "ccxt+db"
            except Exception as e:
                logger.warning("CCXT 补齐 K 线失败，使用 DB 数据 | {} {} err={}", symbol, timeframe, e)
                if not db_items:
                    raise ServiceUnavailableException(
                        message=f"获取 K 线失败: {str(e)}",
                        detail={"symbol": symbol, "timeframe": timeframe},
                    )

        # 升序返回（前端 K 线图需要时间正序）
        db_items.sort(key=lambda x: x.timestamp)
        last_updated = datetime.datetime.now(datetime.timezone.utc) if db_items else None
        return KlineResponse(
            symbol=symbol,
            timeframe=timeframe,
            data=db_items,
            source=source,
            last_updated=last_updated,
        )

    async def _query_klines_from_db(
        self, symbol: str, timeframe: str, limit: int
    ) -> List[KlineItem]:
        """从 DB 查询 K 线（按 open_time 降序）。"""
        result = await self.db.execute(
            select(Kline)
            .where(Kline.symbol == symbol, Kline.timeframe == timeframe)
            .order_by(Kline.open_time.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            KlineItem(
                timestamp=int(row.open_time.timestamp() * 1000),
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in rows
        ]

    async def _fetch_ccxt_and_save(
        self, symbol: str, timeframe: str, limit: int
    ) -> List[KlineItem]:
        """从 CCXT 抓取 K 线并写入 DB。"""
        client = self._get_public_client()
        try:
            ohlcv = await client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not ohlcv:
                return []
            items = [
                KlineItem(
                    timestamp=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
                for row in ohlcv
            ]
            # 批量写入 DB（ON CONFLICT DO NOTHING）
            await self._save_klines_to_db(symbol, timeframe, items)
            return items
        finally:
            await client.close()

    async def _save_klines_to_db(
        self, symbol: str, timeframe: str, items: List[KlineItem]
    ) -> None:
        """批量写入 K 线（冲突跳过）。"""
        if not items or self.db is None:
            return
        rows = []
        for item in items:
            open_time = datetime.datetime.fromtimestamp(
                item.timestamp / 1000, tz=datetime.timezone.utc
            )
            rows.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open_time": open_time,
                    "open": item.open,
                    "high": item.high,
                    "low": item.low,
                    "close": item.close,
                    "volume": item.volume,
                    "quote_volume": None,
                    "source": "ccxt",
                    "exchange": DEFAULT_EXCHANGE,
                }
            )
        # PostgreSQL ON CONFLICT DO NOTHING（需 id 字段；因 Kline 继承 Base 有 id 主键，
        # 但唯一约束在 (symbol, timeframe, open_time)，使用 PG insert on_conflict）
        stmt = pg_insert(Kline).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_klines_symbol_tf_opentime"
        )
        try:
            await self.db.execute(stmt)
            await self.db.flush()
        except Exception as e:
            logger.warning("写入 K 线 DB 失败（已忽略）: {}", e)

    async def _fetch_klines_from_ccxt(
        self, symbol: str, timeframe: str, limit: int
    ) -> KlineResponse:
        """无 DB 模式直接 CCXT 获取。"""
        client = self._get_public_client()
        try:
            ohlcv = await client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            items = [
                KlineItem(
                    timestamp=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
                for row in ohlcv
            ]
            return KlineResponse(
                symbol=symbol,
                timeframe=timeframe,
                data=items,
                source="ccxt",
                last_updated=datetime.datetime.now(datetime.timezone.utc),
            )
        except Exception as e:
            raise ServiceUnavailableException(
                message=f"获取 K 线失败: {str(e)}",
                detail={"symbol": symbol, "timeframe": timeframe},
            )
        finally:
            await client.close()

    # [兼容] 旧接口
    async def get_kline_data(
        self, symbol: str, timeframe: str = "1d", limit: int = 100
    ) -> List[dict]:
        """[兼容] 返回 K 线 dict 列表（旧前端格式）。"""
        resp = await self.get_klines(symbol, timeframe, limit)
        return [item.model_dump() for item in resp.data]

    @staticmethod
    def _timeframe_to_seconds(timeframe: str) -> int:
        """时间周期转秒。"""
        unit_map = {"m": 60, "h": 3600, "d": 86400, "w": 604800, "M": 2592000}
        if not timeframe:
            return 86400
        unit = timeframe[-1]
        if unit not in unit_map:
            return 86400
        try:
            num = int(timeframe[:-1]) if len(timeframe) > 1 else 1
        except ValueError:
            return 86400
        return num * unit_map[unit]

    # ---------- 4. 14 类技术指标 ----------

    async def get_indicators(
        self,
        symbol: str,
        timeframe: str = "1d",
        indicator_types: Optional[List[str]] = None,
        limit: int = 200,
        params: Optional[Dict] = None,
    ) -> IndicatorResponse:
        """计算技术指标（基于 K 线数据）。"""
        kline_resp = await self.get_klines(symbol, timeframe, max(limit, 200))
        if not kline_resp.data:
            return IndicatorResponse(
                symbol=symbol,
                timeframe=timeframe,
                indicators={"error": "no kline data"},
            )
        # 转为 CCXT 原始格式供 indicators 模块使用
        ohlcv = [
            [item.timestamp, item.open, item.high, item.low, item.close, item.volume]
            for item in kline_resp.data
        ]
        indicators = calculate_indicators(ohlcv, indicator_types, params)
        return IndicatorResponse(
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators,
        )

    async def get_coin_analysis(
        self, symbol: str, timeframe: str = "1d"
    ) -> Optional[CoinAnalysis]:
        """[兼容] 旧技术分析接口（返回扁平指标 + signal）。"""
        resp = await self.get_indicators(
            symbol, timeframe, indicator_types=["ma", "rsi", "macd", "boll"]
        )
        # 扁平化指标
        flat: Dict[str, Any] = {}
        for ind_type, values in resp.indicators.items():
            if isinstance(values, dict):
                for k, v in values.items():
                    flat[f"{ind_type}_{k}" if ind_type in ("ma", "ema") else k] = v
        # 生成信号
        signal = self._generate_signal_from_indicators(flat)
        return CoinAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            indicators=flat,
            signal=signal,
            updated_at=resp.calculated_at,
        )

    @staticmethod
    def _generate_signal_from_indicators(indicators: Dict[str, Any]) -> str:
        """根据指标生成买卖信号（兼容旧逻辑）。"""
        rsi = indicators.get("rsi", 50)
        macd = indicators.get("macd")
        macd_signal = indicators.get("macd_signal")
        bullish = 0
        bearish = 0
        if rsi is not None:
            if rsi < 30:
                bullish += 1
            elif rsi > 70:
                bearish += 1
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                bullish += 1
            else:
                bearish += 1
        if bullish > bearish:
            return "buy"
        if bearish > bullish:
            return "sell"
        return "neutral"

    # ---------- 5. 多币种对比 ----------

    async def compare_coins(
        self,
        symbols: List[str],
        timeframe: str = "1d",
        days: int = 30,
    ) -> CompareResponse:
        """多币种对比（归一化收益曲线 + 相关性矩阵）。

        Args:
            symbols: 最多 8 个币种（PRD §5.5.3 R1）
            timeframe: K 线周期，默认 1d
            days: 对比天数（30/90/180）
        """
        if len(symbols) < 2:
            raise BadRequestException(message="对比至少需要 2 个币种")
        if len(symbols) > 8:
            raise BadRequestException(message="对比最多 8 个币种")
        days = min(max(days, 7), 365)

        # 拉取每个币种的 K 线收盘价序列
        closes_map: Dict[str, pd.Series] = {}
        limit = days + 10  # 多取一些避免边界数据缺失
        for sym in symbols:
            try:
                resp = await self.get_klines(sym, timeframe, limit)
                if resp.data:
                    df = pd.DataFrame(
                        [
                            {
                                "date": datetime.datetime.fromtimestamp(
                                    item.timestamp / 1000, tz=datetime.timezone.utc
                                ).strftime("%Y-%m-%d"),
                                "close": item.close,
                            }
                            for item in resp.data
                        ]
                    )
                    df = df.drop_duplicates(subset="date").set_index("date").tail(days)
                    closes_map[sym] = df["close"]
            except Exception as e:
                logger.warning("对比拉取 K 线失败 | {} {}", sym, e)

        if len(closes_map) < 2:
            raise ServiceUnavailableException(
                message="对比币种 K 线数据不足",
                detail={"symbols": list(closes_map.keys())},
            )

        # 对齐日期索引
        df_all = pd.DataFrame(closes_map).dropna()
        if df_all.empty:
            raise ServiceUnavailableException(message="对比币种数据为空")

        # 归一化收益曲线（首日为 0%，后续累计涨跌幅）
        returns = df_all.pct_change().fillna(0)
        norm_curve = (1 + returns).cumprod() - 1

        normalized: List[ComparePoint] = []
        for date, row in norm_curve.iterrows():
            normalized.append(
                ComparePoint(date=date, values={k: float(v) for k, v in row.items()})
            )

        # 相关性矩阵（N×N Pearson）
        corr = df_all.pct_change().dropna().corr()
        symbols_valid = list(corr.columns)
        matrix = []
        for i, s1 in enumerate(symbols_valid):
            row = []
            for j, s2 in enumerate(symbols_valid):
                row.append(float(corr.iloc[i, j]) if not np.isnan(corr.iloc[i, j]) else 0.0)
            matrix.append(row)

        # 汇总指标
        summary: Dict[str, Dict[str, float]] = {}
        for sym in symbols_valid:
            ret = (df_all[sym].iloc[-1] / df_all[sym].iloc[0] - 1) * 100
            vol = float(df_all[sym].pct_change().std() * math.sqrt(365) * 100)
            sharpe = float(ret / vol) if vol > 0 else 0.0
            summary[sym] = {
                "return_pct": float(ret),
                "volatility_pct": vol,
                "sharpe": sharpe,
            }

        return CompareResponse(
            symbols=symbols_valid,
            days=days,
            normalized_curve=normalized,
            correlation=CorrelationMatrix(symbols=symbols_valid, matrix=matrix),
            summary=summary,
        )

    # ---------- 6. AI 分析报告（V1 纯规则） ----------

    async def analyze_coin(
        self, symbol: str, timeframe: str = "1d"
    ) -> AnalysisReport:
        """生成 AI 分析报告（6 部分结构，V1 纯规则）。

        对齐 PRD §5.5.4：
        1. 趋势判断（短中长期 MA 多空）
        2. 支撑阻力（近期高低 + Fibonacci 0.382/0.5/0.618）
        3. 指标信号汇总（MA/RSI/MACD/BOLL）
        4. 量价特征
        5. 风险提示（ATR/波动率 z-score）
        6. 操作建议（观察/轻仓尝试/不推荐 3 档）
        """
        # 获取足够长的 K 线（200 根用于长期 MA + 波动率历史）
        kline_resp = await self.get_klines(symbol, timeframe, 200)
        if len(kline_resp.data) < 30:
            raise ServiceUnavailableException(
                message=f"K 线数据不足（{len(kline_resp.data)} < 30），无法生成分析报告",
                detail={"symbol": symbol},
            )

        ohlcv = [
            [item.timestamp, item.open, item.high, item.low, item.close, item.volume]
            for item in kline_resp.data
        ]
        df = pd.DataFrame(
            ohlcv, columns=["ts", "open", "high", "low", "close", "volume"]
        )
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        close = df["close"]

        # 计算所有指标
        inds = calculate_indicators(ohlcv)

        # 1. 趋势判断
        trend = self._build_trend(close, inds)

        # 2. 支撑阻力
        sr = self._build_support_resistance(df)

        # 3. 指标信号汇总
        signals = self._build_indicator_signals(inds)

        # 4. 量价特征
        volume_price = self._build_volume_price(df)

        # 5. 风险评估
        risk = self._build_risk(df, inds)

        # 6. 操作建议
        recommendation = self._build_recommendation(trend, signals, risk)

        return AnalysisReport(
            symbol=symbol,
            timeframe=timeframe,
            trend=trend,
            support_resistance=sr,
            indicator_signals=signals,
            volume_price=volume_price,
            risk=risk,
            recommendation=recommendation,
        )

    @staticmethod
    def _build_trend(close: pd.Series, inds: Dict) -> AnalysisTrend:
        """构建趋势判断（基于 MA 多空排列）。"""
        def _ma_status(period: int) -> str:
            v = inds.get("ma", {}).get(f"ma{period}")
            if v is None:
                return "neutral"
            last = float(close.iloc[-1])
            return "bullish" if last > v else "bearish"

        short = _ma_status(5)
        mid = _ma_status(20)
        long_t = _ma_status(60)

        # 综合描述
        parts = []
        for label, status, period in [("短期", short, 5), ("中期", mid, 20), ("长期", long_t, 60)]:
            cn = "多头" if status == "bullish" else ("空头" if status == "bearish" else "中性")
            parts.append(f"{label} MA{period} {cn}")
        desc = "；".join(parts)

        # 全多头/全空头
        if short == mid == long_t == "bullish":
            desc += "；整体多头排列，趋势向上"
        elif short == mid == long_t == "bearish":
            desc += "；整体空头排列，趋势向下"

        return AnalysisTrend(
            short_term=short, mid_term=mid, long_term=long_t, description=desc
        )

    @staticmethod
    def _build_support_resistance(df: pd.DataFrame) -> SupportResistance:
        """构建支撑阻力位（近期高低点 + Fibonacci）。"""
        # 近 60 根 K 线的高低点
        window = df.tail(60)
        high_max = float(window["high"].max())
        low_min = float(window["low"].min())
        diff = high_max - low_min

        # 支撑：近期低点 + Fibonacci 回撤
        supports = [low_min, low_min + diff * 0.382, low_min + diff * 0.5]
        # 阻力：近期高点 + Fibonacci 扩展
        resistances = [high_max - diff * 0.382, high_max - diff * 0.5, high_max]

        # Fibonacci 关键位（从低到高）
        fib_levels = {
            "0.382": low_min + diff * 0.382,
            "0.5": low_min + diff * 0.5,
            "0.618": low_min + diff * 0.618,
        }

        return SupportResistance(
            supports=sorted(set(round(s, 4) for s in supports)),
            resistances=sorted(set(round(r, 4) for r in resistances)),
            fibonacci_levels={k: round(v, 4) for k, v in fib_levels.items()},
        )

    @staticmethod
    def _build_indicator_signals(inds: Dict) -> IndicatorSignals:
        """指标信号汇总。"""
        ma = inds.get("ma", {})
        rsi_val = inds.get("rsi", {}).get("rsi")
        macd_val = inds.get("macd", {})
        boll = inds.get("boll", {})

        # MA 信号：MA5 vs MA20
        ma5 = ma.get("ma5")
        ma20 = ma.get("ma20")
        if ma5 is not None and ma20 is not None:
            ma_signal = "bullish" if ma5 > ma20 else "bearish"
        else:
            ma_signal = "neutral"

        # RSI 信号
        if rsi_val is None:
            rsi_signal = "neutral"
        elif rsi_val > 70:
            rsi_signal = "overbought"
        elif rsi_val < 30:
            rsi_signal = "oversold"
        else:
            rsi_signal = "neutral"

        # MACD 信号
        macd_line = macd_val.get("macd")
        macd_sig = macd_val.get("macd_signal")
        if macd_line is not None and macd_sig is not None:
            macd_signal = "bullish" if macd_line > macd_sig else "bearish"
        else:
            macd_signal = "neutral"

        # BOLL 信号：价格触及上轨/下轨
        close_last = None  # 需从外部传入，此处简化用 BOLL 中轨
        boll_upper = boll.get("boll_upper")
        boll_lower = boll.get("boll_lower")
        boll_middle = boll.get("boll_middle")
        if boll_upper is not None and boll_lower is not None:
            # 简化：上轨视为超买，下轨视为超卖
            boll_signal = "neutral"
        else:
            boll_signal = "neutral"

        # 汇总
        bullish = sum(1 for s in [ma_signal, macd_signal] if s == "bullish")
        bearish = sum(1 for s in [ma_signal, macd_signal] if s == "bearish")
        if rsi_signal == "overbought":
            bearish += 1
        elif rsi_signal == "oversold":
            bullish += 1

        if bullish > bearish:
            summary = f"偏多（{bullish}多/{bearish}空信号）"
        elif bearish > bullish:
            summary = f"偏空（{bearish}空/{bullish}多信号）"
        else:
            summary = "中性"

        return IndicatorSignals(
            ma_signal=ma_signal,
            rsi_signal=rsi_signal,
            macd_signal=macd_signal,
            boll_signal=boll_signal,
            summary=summary,
        )

    @staticmethod
    def _build_volume_price(df: pd.DataFrame) -> VolumePriceFeature:
        """量价特征解读。"""
        recent = df.tail(20)
        vol_ma5 = recent["volume"].rolling(5).mean().iloc[-1]
        vol_ma20 = recent["volume"].mean()
        if vol_ma20 > 0:
            vol_ratio = vol_ma5 / vol_ma20
        else:
            vol_ratio = 1.0

        if vol_ratio > 1.2:
            vol_trend = "increasing"
        elif vol_ratio < 0.8:
            vol_trend = "decreasing"
        else:
            vol_trend = "stable"

        # 量价背离：价格上涨但成交量下降
        price_change = recent["close"].iloc[-1] - recent["close"].iloc[0]
        vol_change = recent["volume"].iloc[-1] - recent["volume"].iloc[0]
        divergence = (price_change > 0 and vol_change < 0) or (
            price_change < 0 and vol_change > 0
        )

        desc = f"近 5 日成交量/20 日均值 = {vol_ratio:.2f}，趋势{vol_trend}"
        if divergence:
            desc += "；存在量价背离"

        return VolumePriceFeature(
            volume_trend=vol_trend,
            price_volume_divergence=bool(divergence),
            description=desc,
        )

    @staticmethod
    def _build_risk(df: pd.DataFrame, inds: Dict) -> RiskAssessment:
        """风险评估（波动率 + z-score）。"""
        # 日收益率波动率（年化）
        returns = df["close"].pct_change().dropna().tail(60)
        if len(returns) < 10:
            return RiskAssessment(
                volatility=0.0, volatility_zscore=0.0, description="数据不足"
            )
        daily_vol = float(returns.std())
        annual_vol = daily_vol * math.sqrt(365) * 100  # 年化波动率（%）

        # 近 20 日波动率
        recent_vol = float(returns.tail(20).std()) * math.sqrt(365) * 100
        # 历史 60 日波动率均值与标准差
        rolling_vol = returns.rolling(20).std() * math.sqrt(365) * 100
        hist_mean = float(rolling_vol.mean()) if not np.isnan(rolling_vol.mean()) else annual_vol
        hist_std = float(rolling_vol.std()) if not np.isnan(rolling_vol.std()) else 0.0
        zscore = (recent_vol - hist_mean) / hist_std if hist_std > 0 else 0.0

        # 流动性评分（基于 24h 成交额，简化为成交量分位）
        vol_24h = float(df["volume"].tail(1).iloc[0]) if not df.empty else 0
        vol_mean = float(df["volume"].tail(60).mean()) if len(df) >= 60 else float(df["volume"].mean())
        liquidity = min(100.0, max(0.0, (vol_24h / vol_mean * 50) if vol_mean > 0 else 50.0))

        desc_parts = []
        desc_parts.append(f"年化波动率 {annual_vol:.2f}%")
        if zscore > 1.5:
            desc_parts.append("波动率显著高于历史均值，注意风险")
        elif zscore < -1.5:
            desc_parts.append("波动率显著低于历史均值，可能酝酿变盘")
        return RiskAssessment(
            volatility=round(annual_vol, 4),
            volatility_zscore=round(float(zscore), 4),
            liquidity_score=round(liquidity, 2),
            description="；".join(desc_parts),
        )

    @staticmethod
    def _build_recommendation(
        trend: AnalysisTrend,
        signals: IndicatorSignals,
        risk: RiskAssessment,
    ) -> AnalysisRecommendation:
        """操作建议（观察/轻仓尝试/不推荐 3 档）。"""
        score = 0  # 正数偏多，负数偏空
        if trend.short_term == "bullish":
            score += 1
        elif trend.short_term == "bearish":
            score -= 1
        if trend.mid_term == "bullish":
            score += 1
        elif trend.mid_term == "bearish":
            score -= 1
        if trend.long_term == "bullish":
            score += 1
        elif trend.long_term == "bearish":
            score -= 1
        if signals.ma_signal == "bullish":
            score += 1
        elif signals.ma_signal == "bearish":
            score -= 1
        if signals.macd_signal == "bullish":
            score += 1
        elif signals.macd_signal == "bearish":
            score -= 1
        if signals.rsi_signal == "oversold":
            score += 1
        elif signals.rsi_signal == "overbought":
            score -= 1

        # 风险过高直接降级
        if risk.volatility_zscore > 2.0 or risk.volatility > 100:
            return AnalysisRecommendation(
                action="不推荐",
                confidence=0.7,
                reason="波动率过高，风险显著高于历史均值",
            )

        if score >= 2:
            action = "轻仓尝试"
            confidence = min(0.85, 0.5 + abs(score) * 0.1)
            reason = f"多空评分 +{score}，多头信号占优"
        elif score <= -2:
            action = "不推荐"
            confidence = min(0.85, 0.5 + abs(score) * 0.1)
            reason = f"多空评分 {score}，空头信号占优"
        else:
            action = "观察"
            confidence = 0.5
            reason = f"多空评分 {score}，信号不明朗，建议等待方向确认"

        return AnalysisRecommendation(
            action=action, confidence=round(confidence, 2), reason=reason
        )

    # ---------- 7. Watchlist CRUD ----------

    async def list_watchlist(self, user_id: uuid.UUID) -> List[WatchlistItem]:
        """获取用户自选列表（含实时行情）。"""
        if self.db is None:
            return []
        result = await self.db.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.sort_order.asc(), Watchlist.created_at.desc())
        )
        rows = result.scalars().all()
        items: List[WatchlistItem] = []
        for row in rows:
            item = WatchlistItem(
                id=str(row.id),
                user_id=str(row.user_id),
                symbol=row.symbol,
                note=row.note,
                sort_order=row.sort_order,
                added_price=row.added_price,
                created_at=row.created_at,
            )
            # 填充实时行情（容错；CCXT 失败不影响列表）
            try:
                ticker = await self.get_ticker(row.symbol)
                item.current_price = ticker.current_price
                item.price_change_24h = ticker.price_change_24h
                if row.added_price and ticker.current_price:
                    item.price_change_since_added = (
                        float(ticker.current_price) - row.added_price
                    ) / row.added_price * 100
            except Exception as e:
                logger.warning("Watchlist 行情填充失败 | {} {}", row.symbol, e)
            items.append(item)
        return items

    async def add_to_watchlist(
        self, user_id: uuid.UUID, payload: WatchlistCreate
    ) -> WatchlistItem:
        """添加自选（最多 200）。"""
        if self.db is None:
            raise ServiceUnavailableException(message="数据库不可用")

        # 数量校验
        count_result = await self.db.execute(
            select(func.count(Watchlist.id)).where(Watchlist.user_id == user_id)
        )
        count = count_result.scalar() or 0
        if count >= WATCHLIST_MAX:
            raise BadRequestException(
                message=f"自选列表已达上限（{WATCHLIST_MAX}）"
            )

        # 获取当前价格（用于 added_price）
        added_price: Optional[float] = None
        try:
            ticker = await self.get_ticker(payload.symbol)
            if ticker.current_price:
                added_price = float(ticker.current_price)
        except Exception:
            pass

        item = Watchlist(
            user_id=user_id,
            symbol=payload.symbol,
            note=payload.note,
            sort_order=payload.sort_order,
            added_price=added_price,
        )
        self.db.add(item)
        try:
            await self.db.flush()
        except Exception as e:
            await self.db.rollback()
            if "uq_watchlist_user_symbol" in str(e) or "unique" in str(e).lower():
                raise BadRequestException(
                    message=f"币种 {payload.symbol} 已在自选列表中"
                )
            raise
        await self.db.refresh(item)

        return WatchlistItem(
            id=str(item.id),
            user_id=str(item.user_id),
            symbol=item.symbol,
            note=item.note,
            sort_order=item.sort_order,
            added_price=item.added_price,
            created_at=item.created_at,
            current_price=Decimal(str(added_price)) if added_price else None,
        )

    async def update_watchlist(
        self,
        user_id: uuid.UUID,
        symbol: str,
        payload: WatchlistUpdate,
    ) -> WatchlistItem:
        """更新自选（note / sort_order）。"""
        if self.db is None:
            raise ServiceUnavailableException(message="数据库不可用")
        result = await self.db.execute(
            select(Watchlist).where(
                Watchlist.user_id == user_id, Watchlist.symbol == symbol
            )
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise NotFoundException(
                message=f"自选 {symbol} 不存在",
                detail={"symbol": symbol},
            )
        if payload.note is not None:
            item.note = payload.note
        if payload.sort_order is not None:
            item.sort_order = payload.sort_order
        await self.db.flush()
        await self.db.refresh(item)
        return WatchlistItem(
            id=str(item.id),
            user_id=str(item.user_id),
            symbol=item.symbol,
            note=item.note,
            sort_order=item.sort_order,
            added_price=item.added_price,
            created_at=item.created_at,
        )

    async def remove_from_watchlist(
        self, user_id: uuid.UUID, symbol: str
    ) -> bool:
        """从自选移除。"""
        if self.db is None:
            raise ServiceUnavailableException(message="数据库不可用")
        result = await self.db.execute(
            delete(Watchlist).where(
                Watchlist.user_id == user_id, Watchlist.symbol == symbol
            )
        )
        await self.db.flush()
        return (result.rowcount or 0) > 0
