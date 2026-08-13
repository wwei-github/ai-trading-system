"""币种分析服务。

通过 CCXT 获取行情数据，使用 pandas/numpy 计算技术指标。
"""

from typing import List, Optional

from loguru import logger

from app.core.exceptions import ServiceUnavailableException
from app.exchange.ccxt_client import CCXTClient
from app.schemas.coin import CoinAnalysis, CoinInfo


class CoinService:
    """币种分析服务。

    使用公开市场数据（无需 API Key）获取行情和 K 线，
    本地计算 RSI、MACD、MA 等技术指标。
    """

    DEFAULT_EXCHANGE = "binance"

    def _get_public_client(self, exchange: str = None) -> CCXTClient:
        """获取公开市场数据客户端（无需 API Key）。"""
        return CCXTClient(
            exchange=exchange or self.DEFAULT_EXCHANGE,
            api_key="",
            api_secret="",
            is_testnet=False,
        )

    async def get_coin_info(self, symbol: str) -> Optional[CoinInfo]:
        """获取币种基本信息（含实时行情）。"""
        client = self._get_public_client()
        try:
            ticker = await client.fetch_ticker(symbol)
            return CoinInfo(
                symbol=symbol,
                name=symbol.split("/")[0] if "/" in symbol else symbol,
                current_price=ticker.get("last"),
                price_change_24h=ticker.get("percentage"),
                volume_24h=ticker.get("quoteVolume"),
            )
        except Exception as e:
            logger.error("获取币种信息失败: {} | {}", symbol, e)
            raise ServiceUnavailableException(
                message=f"获取币种信息失败: {str(e)}",
                detail={"symbol": symbol},
            )
        finally:
            await client.close()

    async def get_kline_data(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 100,
    ) -> List[dict]:
        """获取 K 线数据。"""
        client = self._get_public_client()
        try:
            ohlcv = await client.fetch_ohlcv(
                symbol, timeframe=timeframe, limit=limit
            )
            return [
                {
                    "timestamp": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                }
                for row in ohlcv
            ]
        except Exception as e:
            logger.error("获取 K 线失败: {} | {}", symbol, e)
            raise ServiceUnavailableException(
                message=f"获取 K 线数据失败: {str(e)}",
                detail={"symbol": symbol, "timeframe": timeframe},
            )
        finally:
            await client.close()

    async def get_coin_analysis(
        self, symbol: str, timeframe: str = "1d"
    ) -> Optional[CoinAnalysis]:
        """获取币种技术分析（RSI/MACD/MA 等指标）。"""
        client = self._get_public_client()
        try:
            ohlcv = await client.fetch_ohlcv(
                symbol, timeframe=timeframe, limit=100
            )
            if not ohlcv or len(ohlcv) < 30:
                return CoinAnalysis(
                    symbol=symbol,
                    timeframe=timeframe,
                    indicators={},
                    signal="neutral",
                )

            indicators = self._calculate_indicators(ohlcv)
            signal = self._generate_signal(indicators)

            return CoinAnalysis(
                symbol=symbol,
                timeframe=timeframe,
                indicators=indicators,
                signal=signal,
            )
        except Exception as e:
            logger.error("获取技术分析失败: {} | {}", symbol, e)
            raise ServiceUnavailableException(
                message=f"获取技术分析失败: {str(e)}",
                detail={"symbol": symbol, "timeframe": timeframe},
            )
        finally:
            await client.close()

    def _calculate_indicators(self, ohlcv: List[list]) -> dict:
        """计算技术指标。

        Args:
            ohlcv: [[timestamp, open, high, low, close, volume], ...]

        Returns:
            指标字典 {rsi, macd, macd_signal, ma5, ma10, ma20, ma60, ...}
        """
        import numpy as np
        import pandas as pd

        df = pd.DataFrame(
            ohlcv, columns=["ts", "open", "high", "low", "close", "volume"]
        )
        close = df["close"].astype(float)

        indicators = {}

        # 移动平均线
        for period in [5, 10, 20, 60]:
            if len(close) >= period:
                indicators[f"ma{period}"] = float(close.rolling(period).mean().iloc[-1])

        # RSI（14周期）
        if len(close) >= 15:
            delta = close.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(14).mean()
            avg_loss = loss.rolling(14).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            indicators["rsi"] = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

        # MACD
        if len(close) >= 35:
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            hist = macd - signal
            indicators["macd"] = float(macd.iloc[-1])
            indicators["macd_signal"] = float(signal.iloc[-1])
            indicators["macd_hist"] = float(hist.iloc[-1])

        # 布林带（20周期）
        if len(close) >= 20:
            ma20 = close.rolling(20).mean()
            std = close.rolling(20).std()
            indicators["boll_upper"] = float((ma20 + 2 * std).iloc[-1])
            indicators["boll_middle"] = float(ma20.iloc[-1])
            indicators["boll_lower"] = float((ma20 - 2 * std).iloc[-1])

        return indicators

    def _generate_signal(self, indicators: dict) -> str:
        """根据指标生成买卖信号。"""
        rsi = indicators.get("rsi", 50)
        macd = indicators.get("macd")
        macd_signal = indicators.get("macd_signal")

        bullish = 0
        bearish = 0

        # RSI 判断
        if rsi < 30:
            bullish += 1  # 超卖
        elif rsi > 70:
            bearish += 1  # 超买

        # MACD 判断
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                bullish += 1
            else:
                bearish += 1

        if bullish > bearish:
            return "buy"
        elif bearish > bullish:
            return "sell"
        return "neutral"

    async def get_top_coins(self, limit: int = 10) -> List[CoinInfo]:
        """获取热门币种（按成交额排序）。"""
        client = self._get_public_client()
        try:
            await client.load_markets()
            tickers = await client.fetch_tickers()
            # 按成交额排序
            sorted_tickers = sorted(
                [
                    (sym, t)
                    for sym, t in tickers.items()
                    if t.get("quoteVolume")
                ],
                key=lambda x: x[1].get("quoteVolume", 0),
                reverse=True,
            )[:limit]
            return [
                CoinInfo(
                    symbol=sym,
                    name=sym.split("/")[0] if "/" in sym else sym,
                    current_price=t.get("last"),
                    price_change_24h=t.get("percentage"),
                    volume_24h=t.get("quoteVolume"),
                )
                for sym, t in sorted_tickers
            ]
        except Exception as e:
            logger.error("获取热门币种失败: {}", e)
            raise ServiceUnavailableException(
                message=f"获取热门币种失败: {str(e)}"
            )
        finally:
            await client.close()

    async def compare_coins(
        self, symbols: List[str], timeframe: str = "1d"
    ) -> List[dict]:
        """多币种对比。"""
        results = []
        for symbol in symbols:
            try:
                info = await self.get_coin_info(symbol)
                analysis = await self.get_coin_analysis(symbol, timeframe)
                results.append(
                    {
                        "info": info.model_dump() if info else None,
                        "analysis": analysis.model_dump() if analysis else None,
                    }
                )
            except Exception as e:
                results.append(
                    {"symbol": symbol, "error": str(e)}
                )
        return results
