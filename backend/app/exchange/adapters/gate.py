"""Gate.io 交易所适配器。

特性：
- CCXT 类名为 `gate`（不是 `gateio`）
- 支持 spot / swap / futures
- 测试网通过 `set_sandbox_mode(True)`
"""

from typing import Any, Dict, List

from app.exchange.ccxt_base import CCXTBaseAdapter


class GateAdapter(CCXTBaseAdapter):
    """Gate.io 适配器（CCXT 中类名为 gate）。"""

    exchange_name = "gate"
    default_market_type = "spot"

    def _apply_testnet(self, client: Any) -> None:
        if self.is_testnet and hasattr(client, "set_sandbox_mode"):
            client.set_sandbox_mode(True)

    def _extract_permissions(self, balance: Dict[str, Any]) -> List[str]:
        permissions: List[str] = []
        info = balance.get("info") or {}
        if isinstance(info, dict):
            # Gate.io 余额响应直接是币种列表
            # 权限需要通过账户配置单独查询，这里按市场类型推断
            permissions.append(self.market_type)
        return permissions or [self.market_type]

    def _map_error(self, exc: Exception) -> str:
        msg = str(exc).lower()
        code_map = {
            "invalid_api_key": "Gate.io: API Key 无效",
            "invalid_sign": "Gate.io: 签名失败（API Secret 错误）",
            "api_key_invalid": "Gate.io: API Key 无效",
            "ip_not_in_whitelist": "Gate.io: IP 不在白名单",
            "request_limit_exceeded": "Gate.io: 请求过于频繁",
            "insufficient_balance": "Gate.io: 余额不足",
        }
        for code, hint in code_map.items():
            if code in msg:
                return hint
        return super()._map_error(exc)
