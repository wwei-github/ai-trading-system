"""审计日志辅助函数。

提供统一的审计日志写入接口，供各业务模块调用。
"""

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def write_audit_log(
    db: AsyncSession,
    user_id: Optional[uuid.UUID],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    detail: Optional[Any] = None,
    ip: Optional[str] = None,
) -> AuditLog:
    """写入一条审计日志。

    Args:
        db: 数据库会话
        user_id: 操作用户 ID（系统操作可为 None）
        action: 动作：create / update / delete / sync / login 等
        resource_type: 资源类型：account / trade / strategy 等
        resource_id: 资源 ID
        detail: 操作详情（任意可序列化对象）
        ip: 操作 IP

    Returns:
        创建的 AuditLog 实例
    """
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        detail=detail,
        ip=ip,
    )
    db.add(log)
    await db.flush()
    return log


__all__ = ["write_audit_log"]
