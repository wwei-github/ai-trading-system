"""Bybit 交易所适配器。

特性：
- 支持 unified account（统一账户）V5
- 支持 spot / linear / inverse / option
- 测试网通过 `set_sandbox_mode(True)`
- 权限从 `info` 中推断
"""

from typing import Any, Dict, List

from app.exchange.ccxt_base import CCXTBaseAdapter


class BybitAdapter(CCXTBaseAdapter):
    """Bybit 适配器。"""

    exchange_name = "bybit"
    default_market_type = "spot"

    def _build_config(self) -> Dict[str, Any]:
        config = super()._build_config()
        # Bybit V5 统一账户
        config["options"] = {
            "defaultType": self.market_type,
            "recvWindow": "5000",
        }
        return config

    def _apply_testnet(self, client: Any) -> None:
        if self.is_testnet and hasattr(client, "set_sandbox_mode"):
            client.set_sandbox_mode(True)

    def _extract_permissions(self, balance: Dict[str, Any]) -> List[str]:
        permissions: List[str] = []
        info = balance.get("info") or {}
        if isinstance(info, dict):
            result = info.get("result") or {}
            if isinstance(result, dict):
                acct_type = str(result.get("accountType") or "").lower()
                if "spot" in acct_type:
                    permissions.append("spot")
                if "contract" in acct_type or "unified" in acct_type:
                    permissions.extend(["spot", "futures"])
        # marketType 字段
        return permissions or [self.market_type]

    def _map_error(self, exc: Exception) -> str:
        msg = str(exc)
        # Bybit V5 错误码
        code_map = {
            "10001": "Bybit: 参数错误",
            "10003": "Bybit: API Key 无效或已过期",
            "10005": "Bybit: 权限不足",
            "10014": "Bybit: IP 不在白名单",
            "10017": "Bybit: 请求过于频繁",
            "110003": "Bybit: 余额不足",
            "110007": "Bybit: 账户不存在或未开通",
        }
        for code, hint in code_map.items():
            if code in msg:
                return hint
        return super()._map_error(exc)
