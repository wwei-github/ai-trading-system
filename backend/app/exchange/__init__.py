"""交易所连接器模块。

提供：
- `BaseExchangeAdapter`：交易所适配器抽象基类
- `ExchangeFactory`：按交易所类型实例化 adapter
- `CCXTClient`：旧版 CCXT 客户端封装（向后兼容）
- 6 大交易所 adapter 实现
"""

from app.exchange.adapters import (
    BaseExchangeAdapter,
    BinanceAdapter,
    BybitAdapter,
    CoinbaseAdapter,
    ExchangeAdapterError,
    ExchangeFactory,
    GateAdapter,
    HuobiAdapter,
    OKXAdapter,
    SUPPORTED_EXCHANGES,
    WithdrawDisabledError,
)
from app.exchange.ccxt_client import CCXTClient

__all__ = [
    "BaseExchangeAdapter",
    "ExchangeAdapterError",
    "WithdrawDisabledError",
    "ExchangeFactory",
    "SUPPORTED_EXCHANGES",
    "BinanceAdapter",
    "OKXAdapter",
    "BybitAdapter",
    "HuobiAdapter",
    "GateAdapter",
    "CoinbaseAdapter",
    "CCXTClient",
]
