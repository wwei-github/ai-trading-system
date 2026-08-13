"""CCXT 交易所统一客户端封装。

使用 ccxt.async_support 提供真正的异步交易所访问接口，
支持现货和合约，支持测试网。
"""

from typing import Any, Dict, List, Optional

from loguru import logger


class CCXTClient:
    """CCXT 异步交易所客户端封装。

    封装 ccxt.async_support 库，提供统一的交易所 API 调用接口。
    支持动态创建不同交易所的客户端实例。

    用法：
        client = CCXTClient("binance", api_key, api_secret)
        try:
            balance = await client.fetch_balance()
        finally:
            await client.close()
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
        """延迟创建 ccxt 异步交易所客户端实例。"""
        if self._client is not None:
            return self._client

        from ccxt import async_support as ccxt_async

        exchange_class = getattr(ccxt_async, self.exchange_name, None)
        if exchange_class is None:
            raise ValueError(f"不支持的交易所: {self.exchange_name}")

        config: Dict[str, Any] = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }

        if self.passphrase:
            config["password"] = self.passphrase

        self._client = exchange_class(config)

        # 测试网配置
        if self.is_testnet and hasattr(self._client, "set_sandbox_mode"):
            self._client.set_sandbox_mode(True)

        logger.info(
            "交易所客户端初始化: {} (测试网: {})",
            self.exchange_name,
            self.is_testnet,
        )
        return self._client

    async def fetch_balance(self) -> Dict[str, Any]:
        """获取账户余额。"""
        client = self._get_client()
        return await client.fetch_balance()

    async def fetch_trades(
        self, symbol: str, since: Optional[int] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取当前账户的交易历史（已成交订单）。"""
        client = self._get_client()
        return await client.fetch_my_trades(symbol, since=since, limit=limit)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        since: Optional[int] = None,
        limit: int = 100,
    ) -> List[List[Any]]:
        """获取 K 线数据。

        返回格式：[[timestamp, open, high, low, close, volume], ...]
        """
        client = self._get_client()
        return await client.fetch_ohlcv(
            symbol, timeframe, since=since, limit=limit
        )

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """获取行情数据。"""
        client = self._get_client()
        return await client.fetch_ticker(symbol)

    async def fetch_tickers(
        self, symbols: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """获取多个交易对的行情数据。"""
        client = self._get_client()
        return await client.fetch_tickers(symbols)

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """创建订单。"""
        client = self._get_client()
        return await client.create_order(
            symbol, order_type, side, amount, price
        )

    async def cancel_order(
        self, order_id: str, symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """取消订单。"""
        client = self._get_client()
        return await client.cancel_order(order_id, symbol)

    async def load_markets(self) -> Dict[str, Any]:
        """加载市场信息。"""
        client = self._get_client()
        return await client.load_markets()

    async def close(self) -> None:
        """关闭客户端连接，释放资源。"""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning("关闭交易所客户端时出错: {}", e)
            finally:
                self._client = None
                logger.info("交易所客户端已关闭: {}", self.exchange_name)


async def create_ccxt_client_from_account(
    account, decrypt_func
) -> CCXTClient:
    """从 ExchangeAccount 模型创建 CCXT 客户端。

    Args:
        account: ExchangeAccount 模型实例
        decrypt_func: 解密函数（通常为 AccountService.get_decrypted_credentials）

    Returns:
        CCXTClient 实例
    """
    credentials = decrypt_func(account)
    return CCXTClient(
        exchange=account.exchange,
        api_key=credentials["api_key"],
        api_secret=credentials["api_secret"],
        passphrase=credentials.get("passphrase"),
        is_testnet=account.is_testnet,
    )
