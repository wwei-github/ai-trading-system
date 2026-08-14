"""Huobi（火币）交易所适配器。

特性：
- 支持 spot / swap / futures
- 测试网通过 `set_sandbox_mode(True)`
- 权限从账户类型推断
- 注意：CCXT 中类名为 `huobi`，非 `htx`
"""

from typing import Any, Dict, List

from app.exchange.ccxt_base import CCXTBaseAdapter


class HuobiAdapter(CCXTBaseAdapter):
    """Huobi 适配器（CCXT 中类名为 huobi）。"""

    exchange_name = "huobi"
    default_market_type = "spot"

    def _apply_testnet(self, client: Any) -> None:
        if self.is_testnet and hasattr(client, "set_sandbox_mode"):
            client.set_sandbox_mode(True)

    def _extract_permissions(self, balance: Dict[str, Any]) -> List[str]:
        permissions: List[str] = []
        info = balance.get("info") or {}
        if isinstance(info, dict):
            data = info.get("data") or []
            if isinstance(data, list) and data:
                first = data[0] if isinstance(data[0], dict) else {}
                account_type = str(first.get("type") or "").lower()
                if "spot" in account_type:
                    permissions.append("spot")
                if "margin" in account_type:
                    permissions.append("margin")
                if "swap" in account_type or "future" in account_type:
                    permissions.append("futures")
        return permissions or [self.market_type]

    def _map_error(self, exc: Exception) -> str:
        msg = str(exc)
        # Huobi 常见错误码
        code_map = {
            "invalid-api-key": "Huobi: API Key 无效",
            "signature-failure": "Huobi: 签名失败（API Secret 错误）",
            "api-signature-not-valid": "Huobi: 签名失败",
            "illegal-api-key": "Huobi: API Key 无效",
            "no-permission": "Huobi: 权限不足",
            "ip-forbidden": "Huobi: IP 不在白名单",
            "base-request-limit": "Huobi: 请求过于频繁",
            "insufficient-balance": "Huobi: 余额不足",
        }
        for code, hint in code_map.items():
            if code in msg.lower():
                return hint
        return super()._map_error(exc)
