"""Coinbase 交易所适配器。

特性：
- CCXT 类名为 `coinbase`（或 `coinbasepro` / `coinbaseexchange`）
- 需要 passphrase（Coinbase Pro 创建 API Key 时设置）
- 权限从 `info` 推断
"""

from typing import Any, Dict, List

from app.exchange.base import ExchangeAdapterError
from app.exchange.ccxt_base import CCXTBaseAdapter


class CoinbaseAdapter(CCXTBaseAdapter):
    """Coinbase 适配器（CCXT 中类名为 coinbase）。"""

    exchange_name = "coinbase"
    requires_passphrase = True
    default_market_type = "spot"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Coinbase Pro API passphrase 非必填（取决于 Key 类型），
        # 但如果使用 Pro Key 则需要 passphrase
        # 这里允许 passphrase 为空，运行时若有 401 再提示

    def _build_config(self) -> Dict[str, Any]:
        config = super()._build_config()
        if self.passphrase:
            config["password"] = self.passphrase
        return config

    def _apply_testnet(self, client: Any) -> None:
        if self.is_testnet and hasattr(client, "set_sandbox_mode"):
            client.set_sandbox_mode(True)

    def _extract_permissions(self, balance: Dict[str, Any]) -> List[str]:
        permissions: List[str] = []
        info = balance.get("info") or {}
        if isinstance(info, dict):
            data = info.get("data") or []
            if isinstance(data, list):
                permissions.append("spot")
        return permissions or ["spot"]

    def _map_error(self, exc: Exception) -> str:
        msg = str(exc).lower()
        if "invalid api key" in msg or "authentication error" in msg:
            return "Coinbase: API Key 或 passphrase 无效"
        if "invalid signature" in msg or "signature" in msg:
            return "Coinbase: 签名失败（API Secret 错误）"
        if "permission" in msg:
            return "Coinbase: 权限不足"
        if "unauthorized" in msg:
            return "Coinbase: 未授权（请检查 API Key / passphrase）"
        return super()._map_error(exc)
