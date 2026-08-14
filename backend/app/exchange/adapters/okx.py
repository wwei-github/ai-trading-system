"""OKX 交易所适配器。

特性：
- 需要 passphrase（创建 API Key 时设置）
- 支持 spot / swap / futures
- 测试网需通过 `set_sandbox_mode(True)` 开启
- 权限从 `info` 顶层字段解析
"""

from typing import Any, Dict, List

from app.exchange.base import ExchangeAdapterError
from app.exchange.ccxt_base import CCXTBaseAdapter


class OKXAdapter(CCXTBaseAdapter):
    """OKX 适配器。"""

    exchange_name = "okx"
    requires_passphrase = True
    default_market_type = "spot"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.passphrase:
            raise ExchangeAdapterError(
                "OKX 交易所需要 passphrase（创建 API Key 时设置的口令）"
            )

    def _build_config(self) -> Dict[str, Any]:
        config = super()._build_config()
        # OKX 需显式 password
        config["password"] = self.passphrase
        return config

    def _apply_testnet(self, client: Any) -> None:
        if self.is_testnet and hasattr(client, "set_sandbox_mode"):
            client.set_sandbox_mode(True)

    def _extract_permissions(self, balance: Dict[str, Any]) -> List[str]:
        """OKX 账户权限从 `info.data[0].ctType` 或顶层权限字段推断。"""
        permissions: List[str] = []
        info = balance.get("info") or {}
        if isinstance(info, dict):
            data = info.get("data") or []
            if isinstance(data, list) and data:
                first = data[0] if isinstance(data[0], dict) else {}
                ct_type = first.get("ctType") or ""
                if first.get("acctLv"):
                    acct_lv = str(first.get("acctLv"))
                    # 1=现货, 2=单币种保证金, 3=跨币种保证金, 4=组合保证金
                    if acct_lv == "1":
                        permissions.append("spot")
                    else:
                        permissions.extend(["spot", "margin", "swap", "futures"])
                if "swap" in ct_type.lower() or "futures" in ct_type.lower():
                    if "futures" not in permissions:
                        permissions.append("futures")
        return permissions

    def _map_error(self, exc: Exception) -> str:
        """OKX 错误码中文映射。"""
        msg = str(exc)
        # OKX 常见错误码（返回在 msg 中以 "code: xxx" 形式）
        code_map = {
            "50102": "OKX: 账户不存在",
            "50111": "OKX: API Key 无效",
            "50112": "OKX: passphrase 错误",
            "50113": "OKX: 签名失败（API Secret 错误）",
            "50119": "OKX: 请求过于频繁",
            "50117": "OKX: 余额不足",
            "50011": "OKX: 账户被冻结",
            "70006": "OKX: IP 不在白名单",
        }
        for code, hint in code_map.items():
            if code in msg:
                return hint
        return super()._map_error(exc)
