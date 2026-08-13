"""CCXT 交易所统一客户端封装。

提供对多交易所的统一访问接口，支持现货和合约。
"""

from typing import Any, Dict, List, Optional

from loguru import logger


class CCXTClient:
    """CCXT 交易所客户端封装。

    封装 ccxt 库，提供统一的交易所 API 调用接口。
    支持动态创建不同交易所的客户端实例。
    """

    def __init__(
        self,
        exchange: str,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        is_testnet: bool = False,
    ):
        """初始化交易所客户端。

        Args:
            exchange: 交易所名称（binance / okx / bybit 等）
            api_key: API Key
            api_secret: API Secret
            passphrase: 口令（OKX 等交易所需要）
            is_testnet: 是否使用测试网
        """
        self.exchange_name = exchange
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.is_testnet = is_testnet
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """延迟创建 ccxt 交易所客户端实例。"""
        if self._client is not None:
            return self._client

        import ccxt

        exchange_class = getattr(ccxt, self.exchange_name, None)
        if exchange_class is None:
            raise ValueError(f"不支持的交易所: {self.exchange_name}")

        config: Dict[str, Any] = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
        }

        if self.passphrase:
            config["password"] = self.passphrase

        if self.is_testnet:
            config.setdefault("options", {})["defaultType"] = "spot"

        self._client = exchange_class(config)

        # 测试网配置
        if self.is_testnet and hasattr(self._client, "set_sandbox_mode"):
            self._client.set_sandbox_mode(True)

        logger.info("交易所客户端初始化: {} (测试网: {})", self.exchange_name, self.is_testnet)
        return self._client

    async def fetch_balance(self) -> Dict[str, Any]:
        """获取账户余额。"""
        # TODO: 实现异步获取余额
        client = self._get_client()
        return await client.fetch_balance() if hasattr(client, "fetch_balance") else {}

    async def fetch_trades(
        self, symbol: str, since: Optional[int] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取交易历史。"""
        # TODO: 实现异步获取交易历史
        client = self._get_client()
        return (
            await client.fetch_my_trades(symbol, since=since, limit=limit)
            if hasattr(client, "fetch_my_trades")
            else []
        )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        since: Optional[int] = None,
        limit: int = 100,
    ) -> List[List[Any]]:
        """获取 K 线数据。"""
        # TODO: 实现异步获取 K 线
        client = self._get_client()
        return (
            await client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            if hasattr(client, "fetch_ohlcv")
            else []
        )

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """获取行情数据。"""
        # TODO: 实现异步获取行情
        client = self._get_client()
        return (
            await client.fetch_ticker(symbol)
            if hasattr(client, "fetch_ticker")
            else {}
        )

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """创建订单。"""
        # TODO: 实现下单逻辑
        client = self._get_client()
        return (
            await client.create_order(symbol, order_type, side, amount, price)
            if hasattr(client, "create_order")
            else {}
        )

    async def close(self) -> None:
        """关闭客户端连接。"""
        if self._client is not None:
            # ccxt 客户端通常无需显式关闭
            self._client = None
            logger.info("交易所客户端已关闭: {}", self.exchange_name)
