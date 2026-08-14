"""审计日志辅助函数。

提供统一的审计日志写入接口，供各业务模块调用。
所有写入审计的 detail 会自动脱敏敏感字段（api_key / api_secret /
passphrase / password / token 等），避免密文或明文泄漏。
"""

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


# 10 类标准动作（对齐方案 §5.9.4）
AUDIT_ACTIONS = {
    "login", "logout", "register",
    "create", "update", "delete",
    "sync", "export", "import",
    "config_change",
}

# 审计日志中需自动脱敏的字段名（小写匹配）
SENSITIVE_FIELDS = {
    "api_key", "apikey", "api_secret", "apisecret", "secret",
    "passphrase", "password", "pwd",
    "token", "access_token", "refresh_token",
    "private_key", "mnemonic", "seed",
    "totp_secret", "otp_secret",
}


def mask_sensitive(value: Any) -> str:
    """对敏感值进行脱敏（统一返回 ***）。"""
    return "***"


def sanitize_detail(detail: Any) -> Any:
    """递归清理 detail 中的敏感字段。

    支持 dict / list / tuple 嵌套结构；遇到 SENSITIVE_FIELDS 中的键
    自动替换为 '***'。
    """
    if isinstance(detail, dict):
        return {
            k: (mask_sensitive(v) if _is_sensitive_key(k) else sanitize_detail(v))
            for k, v in detail.items()
        }
    if isinstance(detail, list):
        return [sanitize_detail(item) for item in detail]
    if isinstance(detail, tuple):
        return tuple(sanitize_detail(item) for item in detail)
    return detail


def _is_sensitive_key(key: Any) -> bool:
    """判断字段名是否属于敏感字段。"""
    if not isinstance(key, str):
        return False
    return key.lower().strip() in SENSITIVE_FIELDS


async def write_audit_log(
    db: AsyncSession,
    user_id: Optional[uuid.UUID],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    detail: Optional[Any] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """写入一条审计日志（detail 自动脱敏）。

    Args:
        db: 数据库会话
        user_id: 操作用户 ID（系统操作可为 None）
        action: 动作：login / logout / register / create / update / delete / sync / export / import / config_change
        resource_type: 资源类型：account / trade / strategy 等
        resource_id: 资源 ID
        detail: 操作详情（任意可序列化对象，可含 before/after）
        ip: 操作 IP
        user_agent: User-Agent

    Returns:
        创建的 AuditLog 实例
    """
    # 自动脱敏敏感字段（api_key / api_secret / passphrase / password / token 等）
    safe_detail = sanitize_detail(detail) if detail is not None else None

    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        detail=safe_detail,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(log)
    await db.flush()
    return log


def diff_payload(before: Optional[dict], after: Optional[dict]) -> dict:
    """构建 before/after diff 详情（简化版，不依赖 deepdiff）。"""
    return {"before": sanitize_detail(before) or {}, "after": sanitize_detail(after) or {}}


__all__ = [
    "write_audit_log",
    "diff_payload",
    "sanitize_detail",
    "mask_sensitive",
    "AUDIT_ACTIONS",
    "SENSITIVE_FIELDS",
]
