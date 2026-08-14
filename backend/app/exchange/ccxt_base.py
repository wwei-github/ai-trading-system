"""基于 CCXT 的通用交易所适配器基类。

大部分交易所的行为可通过 CCXT 统一抽象，仅需在子类中覆盖少量差异
（如测试网配置、市场类型默认值、passphrase 是否必需、错误码映射）。
"""

import time
from typing import Any, Dict, List, Optional

from loguru import logger

from app.exchange.base import (
    BaseExchangeAdapter,
    ExchangeAdapterError,
)


class CCXTBaseAdapter(BaseExchangeAdapter):
    """基于 CCXT 的通用适配器基类。

    子类只需设置 `exchange_name` 并按需覆盖以下方法：
      - `_build_config()` : 自定义 ccxt 配置
      - `_apply_testnet()` : 测试网开关实现
      - `_map_error()` : 错误码中文映射
      - `_extract_permissions()` : 从余额响应解析权限列表
    """

    # CCXT 模块中的交易所类名（小写）
    exchange_name: str = ""

    def _get_ccxt_class(self):
        """动态加载 ccxt 异步交易所类。"""
        from ccxt import async_support as ccxt_async

        cls = getattr(ccxt_async, self.exchange_name, None)
        if cls is None:
            raise ExchangeAdapterError(
                f"CCXT 不支持的交易所: {self.exchange_name}"
            )
        return cls

    def _build_config(self) -> Dict[str, Any]:
        """构建 ccxt 配置字典。子类可覆盖以定制。"""
        config: Dict[str, Any] = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": self.market_type},
        }
        if self.requires_passphrase and self.passphrase:
            config["password"] = self.passphrase
        return config

    def _apply_testnet(self, client: Any) -> None:
        """应用测试网配置。子类可覆盖以实现交易所特殊处理。"""
        if self.is_testnet and hasattr(client, "set_sandbox_mode"):
            client.set_sandbox_mode(True)

    def _get_client(self) -> Any:
        """延迟创建 ccxt 异步客户端实例。"""
        if self._client is not None:
            return self._client

        cls = self._get_ccxt_class()
        self._client = cls(self._build_config())
        self._apply_testnet(self._client)
        logger.info(
            "交易所客户端初始化: {} (testnet={} market={})",
            self.exchange_name,
            self.is_testnet,
            self.market_type,
        )
        return self._client

    # ---------- 生命周期 ----------

    async def connect(self) -> Dict[str, Any]:
        """连接测试：拉取余额 + 解析权限 + 计算延迟。"""
        client = self._get_client()
        start = time.monotonic()
        try:
            balance = await client.fetch_balance()
            latency_ms = int((time.monotonic() - start) * 1000)
            permissions = self._extract_permissions(balance)
            return {
                "success": True,
                "exchange": self.exchange_name,
                "is_testnet": self.is_testnet,
                "latency_ms": latency_ms,
                "permissions": permissions,
                "message": "连接成功",
                "total": self._normalize_balance(balance.get("total", {})),
            }
        except Exception as e:
            raise ExchangeAdapterError(self._map_error(e)) from e

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning("关闭 {} 客户端时出错: {}", self.exchange_name, e)
            finally:
                self._client = None

    # ---------- 行情接口 ----------

    async def get_balance(self) -> Dict[str, Any]:
        client = self._get_client()
        try:
            balance = await client.fetch_balance()
            return {
                "exchange": self.exchange_name,
                "is_testnet": self.is_testnet,
                "total": self._normalize_balance(balance.get("total", {})),
                "free": self._normalize_balance(balance.get("free", {})),
                "used": self._normalize_balance(balance.get("used", {})),
                "info": balance.get("info", {}),
            }
        except Exception as e:
            raise ExchangeAdapterError(self._map_error(e)) from e

    async def get_tickers(
        self, symbols: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        client = self._get_client()
        try:
            return await client.fetch_tickers(symbols)
        except Exception as e:
            raise ExchangeAdapterError(self._map_error(e)) from e

    async def fetch_kline(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[int] = None,
        limit: int = 500,
    ) -> List[List[Any]]:
        client = self._get_client()
        try:
            return await client.fetch_ohlcv(
                symbol, timeframe, since=since, limit=limit
            )
        except Exception as e:
            raise ExchangeAdapterError(self._map_error(e)) from e

    # ---------- 订单/交易接口 ----------

    async def get_orders(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        client = self._get_client()
        try:
            return await client.fetch_orders(symbol, since=since, limit=limit)
        except Exception as e:
            raise ExchangeAdapterError(self._map_error(e)) from e

    async def get_trades(
        self, symbol: Optional[str] = None, since: Optional[int] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        client = self._get_client()
        try:
            return await client.fetch_my_trades(symbol, since=since, limit=limit)
        except Exception as e:
            raise ExchangeAdapterError(self._map_error(e)) from e

    async def place_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        client = self._get_client()
        try:
            return await client.create_order(
                symbol, order_type, side, amount, price
            )
        except Exception as e:
            raise ExchangeAdapterError(self._map_error(e)) from e

    async def cancel_order(
        self, order_id: str, symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        client = self._get_client()
        try:
            return await client.cancel_order(order_id, symbol)
        except Exception as e:
            raise ExchangeAdapterError(self._map_error(e)) from e

    # ---------- 辅助方法（子类可覆盖） ----------

    def _extract_permissions(self, balance: Dict[str, Any]) -> List[str]:
        """从余额响应解析权限列表。子类可按交易所 info 字段定制。"""
        permissions: List[str] = []
        info = balance.get("info", {})
        if isinstance(info, dict):
            if info.get("canTrade"):
                permissions.append("spot")
            if info.get("canTradeFutures") or info.get("canTradeMargin"):
                permissions.append("futures")
        return permissions

    def _normalize_balance(self, raw: Dict[str, Any]) -> Dict[str, float]:
        """标准化余额：过滤非零项并转为 float。"""
        return {
            k: float(v)
            for k, v in (raw or {}).items()
            if v is not None and float(v) > 0
        }

    def _map_error(self, exc: Exception) -> str:
        """将交易所错误映射为中文提示。子类可覆盖以定制。"""
        msg = str(exc)
        # 通用错误码映射
        lower_msg = msg.lower()
        if "invalid api key" in lower_msg or "invalidkey" in lower_msg:
            return "API Key 无效，请检查密钥是否正确"
        if "signature" in lower_msg:
            return "API Secret 错误或签名失败"
        if "permission" in lower_msg:
            return "API Key 权限不足，请在交易所后台开启对应权限"
        if "ip" in lower_msg and ("not allowed" in lower_msg or "whitelist" in lower_msg):
            return "IP 不在白名单，请在交易所后台添加本机 IP"
        if "rate limit" in lower_msg or "too many" in lower_msg:
            return "请求频率超限，请稍后重试"
        if "nonce" in lower_msg:
            return "时间戳错误，请检查服务器时间"
        if "insufficient" in lower_msg:
            return "余额不足"
        if "timeout" in lower_msg or "timed out" in lower_msg:
            return "请求超时，请检查网络或稍后重试"
        if "ddos" in lower_msg:
            return "交易所临时限流，请稍后重试"
        return f"{self.exchange_name} 请求失败: {msg}"
