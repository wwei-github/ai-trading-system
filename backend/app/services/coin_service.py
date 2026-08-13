"""币种分析服务。"""

from typing import Optional

from app.schemas.coin import CoinAnalysis, CoinInfo


class CoinService:
    """币种分析服务。

    获取币种行情、技术指标分析。
    """

    async def get_coin_info(self, symbol: str) -> Optional[CoinInfo]:
        """获取币种基本信息。"""
        # TODO: 通过 CCXT 获取行情数据
        return None

    async def get_coin_analysis(
        self, symbol: str, timeframe: str = "1d"
    ) -> Optional[CoinAnalysis]:
        """获取币种技术分析。"""
        # TODO: 计算技术指标（RSI、MACD 等）
        return None

    async def get_top_coins(self, limit: int = 10) -> list:
        """获取热门币种。"""
        # TODO: 按交易量排序获取热门币种
        return []
