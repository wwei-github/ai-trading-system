"""交易所适配器集合。

提供 6 大交易所（Binance/OKX/Bybit/Huobi/Gate/Coinbase）的统一适配器，
以及 `ExchangeFactory` 工厂模式按交易所类型实例化 adapter。

用法：
    from app.exchange.adapters import ExchangeFactory

    adapter = ExchangeFactory.create(
        exchange="binance",
        api_key="xxx",
        api_secret="xxx",
        is_testnet=True,
    )
    try:
        result = await adapter.connect()
    finally:
        await adapter.close()
"""

from typing import Any, Dict, Optional, Type

from app.exchange.base import (
    BaseExchangeAdapter,
    ExchangeAdapterError,
    WithdrawDisabledError,
)
from app.exchange.adapters.binance import BinanceAdapter
from app.exchange.adapters.bybit import BybitAdapter
from app.exchange.adapters.coinbase import CoinbaseAdapter
from app.exchange.adapters.gate import GateAdapter
from app.exchange.adapters.huobi import HuobiAdapter
from app.exchange.adapters.okx import OKXAdapter

# 支持的交易所清单
SUPPORTED_EXCHANGES: Dict[str, Type[BaseExchangeAdapter]] = {
    "binance": BinanceAdapter,
    "okx": OKXAdapter,
    "bybit": BybitAdapter,
    "huobi": HuobiAdapter,
    "gate": GateAdapter,
    "coinbase": CoinbaseAdapter,
}

# 各交易所别名映射（用户输入兜底）
EXCHANGE_ALIASES: Dict[str, str] = {
    "binance": "binance",
    "bnb": "binance",
    "okex": "okx",
    "okx": "okx",
    "bybit": "bybit",
    "huobi": "huobi",
    "htx": "huobi",  # 火币已更名为 HTX
    "gate": "gate",
    "gateio": "gate",
    "gate.io": "gate",
    "coinbase": "coinbase",
    "coinbasepro": "coinbase",
    "coinbase_pro": "coinbase",
}


class ExchangeFactory:
    """交易所适配器工厂。

    按交易所名称实例化对应的 adapter。
    未知交易所抛出 `ExchangeAdapterError`。
    """

    @staticmethod
    def create(
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        is_testnet: bool = False,
        market_type: str = "spot",
        **kwargs: Any,
    ) -> BaseExchangeAdapter:
        """创建交易所适配器实例。

        Args:
            exchange: 交易所名称（支持别名，如 okex / htx / gateio）
            api_key: API Key
            api_secret: API Secret
            passphrase: 口令（OKX / Coinbase 需要）
            is_testnet: 是否使用测试网
            market_type: 市场类型 spot / futures / margin

        Returns:
            交易所适配器实例

        Raises:
            ExchangeAdapterError: 不支持的交易所
        """
        if not exchange:
            raise ExchangeAdapterError("交易所名称不能为空")

        # 别名归一化
        normalized = EXCHANGE_ALIASES.get(exchange.lower().strip())
        if normalized is None:
            raise ExchangeAdapterError(
                f"不支持的交易所: {exchange}。"
                f"当前支持: {', '.join(SUPPORTED_EXCHANGES.keys())}"
            )

        adapter_cls = SUPPORTED_EXCHANGES[normalized]
        return adapter_cls(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            is_testnet=is_testnet,
            market_type=market_type,
        )

    @staticmethod
    def is_supported(exchange: str) -> bool:
        """判断交易所是否受支持。"""
        return exchange.lower().strip() in EXCHANGE_ALIASES

    @staticmethod
    def _normalize_name(exchange: str) -> str:
        """将交易所名称（或别名）归一化为标准名称。

        Raises:
            ExchangeAdapterError: 不支持的交易所
        """
        normalized = EXCHANGE_ALIASES.get(exchange.lower().strip())
        if normalized is None:
            raise ExchangeAdapterError(f"不支持的交易所: {exchange}")
        return normalized

    @staticmethod
    def supported_exchanges() -> list:
        """返回支持的交易所列表（去重）。"""
        return list(SUPPORTED_EXCHANGES.keys())


__all__ = [
    "SUPPORTED_EXCHANGES",
    "EXCHANGE_ALIASES",
    "ExchangeFactory",
    "BaseExchangeAdapter",
    "ExchangeAdapterError",
    "WithdrawDisabledError",
    "BinanceAdapter",
    "OKXAdapter",
    "BybitAdapter",
    "HuobiAdapter",
    "GateAdapter",
    "CoinbaseAdapter",
]
