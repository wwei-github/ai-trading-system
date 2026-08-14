"""交易所适配器抽象基类。

所有交易所适配器应继承 `BaseExchangeAdapter` 并实现统一接口。
V1 默认禁用提币接口，调用时抛出 `WithdrawDisabledError`。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class WithdrawDisabledError(Exception):
    """提币接口默认禁用异常。

    V1 出于资金安全考虑，所有 adapter 的 `withdraw` / `transfer` 接口
    固定抛出此异常；配置开关无法绕过；代码 review + 单测双重锁定。
    """


class ExchangeAdapterError(Exception):
    """交易所适配器通用异常。"""


class BaseExchangeAdapter(ABC):
    """交易所适配器抽象基类。

    定义统一接口：connect / get_balance / get_orders / get_trades /
    get_tickers / fetch_kline / place_order / cancel_order / withdraw。
    """

    # 子类必须覆盖此属性
    exchange_name: str = ""
    # 是否需要 passphrase（OKX/Coinbase 需要）
    requires_passphrase: bool = False
    # 默认市场类型
    default_market_type: str = "spot"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        is_testnet: bool = False,
        market_type: str = "spot",
    ):
        """初始化适配器。

        Args:
            api_key: API Key
            api_secret: API Secret
            passphrase: 口令（OKX / Coinbase 需要，其他交易所忽略）
            is_testnet: 是否使用测试网
            market_type: 市场类型 spot / futures / margin
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.is_testnet = is_testnet
        self.market_type = market_type or self.default_market_type
        self._client: Optional[Any] = None

    # ---------- 生命周期 ----------

    @abstractmethod
    async def connect(self) -> Dict[str, Any]:
        """连接测试。

        Returns:
            包含 success / latency_ms / permissions / message 的字典
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """关闭客户端连接，释放资源。"""
        raise NotImplementedError

    # ---------- 行情接口 ----------

    @abstractmethod
    async def get_balance(self) -> Dict[str, Any]:
        """获取账户余额。

        Returns:
            标准化余额字典 {total/free/used: {SYMBOL: amount}}
        """
        raise NotImplementedError

    @abstractmethod
    async def get_tickers(
        self, symbols: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """获取一个或多个交易对行情。"""
        raise NotImplementedError

    @abstractmethod
    async def fetch_kline(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[int] = None,
        limit: int = 500,
    ) -> List[List[Any]]:
        """获取 K 线数据。

        Returns:
            [[timestamp, open, high, low, close, volume], ...]
        """
        raise NotImplementedError

    # ---------- 订单/交易接口 ----------

    @abstractmethod
    async def get_orders(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取订单列表（未成交+已成交）。"""
        raise NotImplementedError

    @abstractmethod
    async def get_trades(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取已成交交易记录。"""
        raise NotImplementedError

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """下单。"""
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(
        self, order_id: str, symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """撤单。"""
        raise NotImplementedError

    # ---------- 默认禁用的提币接口 ----------

    async def withdraw(
        self,
        currency: str,
        amount: float,
        address: str,
        tag: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """提币接口（V1 默认禁用）。

        V1 出于资金安全考虑固定抛出异常；
        即使存在配置开关也无法绕过此限制（双重锁定）。
        """
        raise WithdrawDisabledError(
            f"V1 版本默认禁用提币接口（交易所: {self.exchange_name}）。"
            "如需启用请联系管理员并升级到 V2 安全版本。"
        )

    async def transfer(
        self, code: str, amount: float, from_account: str, to_account: str
    ) -> Dict[str, Any]:
        """资金划转接口（V1 默认禁用）。"""
        raise WithdrawDisabledError(
            f"V1 版本默认禁用资金划转接口（交易所: {self.exchange_name}）。"
        )

    async def __aenter__(self) -> "BaseExchangeAdapter":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
