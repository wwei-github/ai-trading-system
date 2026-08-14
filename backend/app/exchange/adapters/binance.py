"""Binance 交易所适配器。

特性：
- 现货/合约（USDⓈ-M）双市场
- 测试网：spot testnet / futures testnet
- 权限从 `accountInfo.permissions` 解析
"""

from typing import Any, Dict, List

from app.exchange.ccxt_base import CCXTBaseAdapter


class BinanceAdapter(CCXTBaseAdapter):
    """Binance 适配器。"""

    exchange_name = "binance"
    default_market_type = "spot"

    def _apply_testnet(self, client: Any) -> None:
        """Binance 测试网需通过 set_sandbox_mode 开启。"""
        if self.is_testnet and hasattr(client, "set_sandbox_mode"):
            client.set_sandbox_mode(True)

    def _extract_permissions(self, balance: Dict[str, Any]) -> List[str]:
        """Binance 账户权限从 `info.permissions` 数组解析。"""
        permissions: List[str] = []
        info = balance.get("info") or {}
        if isinstance(info, dict):
            raw_perms = info.get("permissions") or []
            if isinstance(raw_perms, list):
                for p in raw_perms:
                    p_lower = str(p).lower()
                    if "spot" in p_lower:
                        permissions.append("spot")
                    if "margin" in p_lower:
                        permissions.append("margin")
                    if "future" in p_lower:
                        permissions.append("futures")
            # 旧版字段
            if info.get("canTrade") and "spot" not in permissions:
                permissions.append("spot")
            if info.get("canDeposit"):
                permissions.append("deposit")
            if info.get("canWithdraw"):
                permissions.append("withdraw")
        return permissions

    def _map_error(self, exc: Exception) -> str:
        """Binance 错误码中文映射。"""
        msg = str(exc)
        code = getattr(exc, "code", None)
        # Binance 常见错误码
        code_map = {
            -2015: "API Key 无效或权限不足",
            -1022: "API Secret 签名失败",
            -2010: "余额不足或挂单数量过小",
            -1003: "请求过于频繁，请稍后重试",
            -1121: "无效的交易对",
            -1100: "参数非法",
            -2014: "API Key 格式错误",
        }
        if code in code_map:
            return f"Binance: {code_map[code]}"
        if "-2015" in msg:
            return "Binance: API Key 无效或权限不足"
        if "-1022" in msg:
            return "Binance: API Secret 签名失败"
        return super()._map_error(exc)
