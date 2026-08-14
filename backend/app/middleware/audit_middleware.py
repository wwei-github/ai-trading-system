"""审计日志中间件。

对关键写操作（POST/PUT/PATCH/DELETE）路由自动记录审计日志。
通过路由 tag 自动识别 resource_type；失败请求也会记录。
"""

import time
import uuid
from typing import Optional

from fastapi import Request, Response
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.security import decode_token
from app.models.user import User
from app.utils.audit import write_audit_log


# 需要审计的方法
AUDIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# 路径前缀 → resource_type 映射
PATH_PREFIX_MAP = {
    "/api/v1/accounts": "account",
    "/api/v1/trades": "trade",
    "/api/v1/strategies": "strategy",
    "/api/v1/books": "book",
    "/api/v1/ai": "ai",
    "/api/v1/system": "system",
    "/api/v1/users": "user",
    "/api/v1/auth": "auth",
}


def _resolve_resource_type(path: str) -> Optional[str]:
    for prefix, rtype in PATH_PREFIX_MAP.items():
        if path.startswith(prefix):
            return rtype
    return None


def _resolve_action(method: str, path: str) -> str:
    """根据方法推断动作。"""
    if path.endswith("/login"):
        return "login"
    if path.endswith("/logout"):
        return "logout"
    if path.endswith("/register"):
        return "register"
    if path.endswith("/import") or "/import" in path:
        return "import"
    if path.endswith("/export") or "/export" in path:
        return "export"
    if path.endswith("/sync") or "/sync" in path:
        return "sync"
    method_map = {
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }
    return method_map.get(method.upper(), "unknown")


async def _resolve_user_id(request: Request) -> Optional[uuid.UUID]:
    """从 Authorization 头解析 user_id（不查 DB，避免性能损耗）。"""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except Exception:
        return None


async def audit_middleware(request: Request, call_next) -> Response:
    """审计中间件。

    仅对配置的关键方法记录；不阻塞业务请求（异常不影响主流程）。
    """
    method = request.method.upper()
    path = request.url.path

    # 非审计方法直接放行
    if method not in AUDIT_METHODS:
        return await call_next(request)

    # 健康检查等非业务路径跳过
    if path in ("/", "/health") or path.startswith("/docs") or path.startswith("/openapi"):
        return await call_next(request)

    # 解析用户
    user_id = await _resolve_user_id(request)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:200]

    # 执行业务
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        # 业务异常已被全局处理器捕获，这里不会到达
        raise

    duration_ms = (time.time() - start) * 1000

    # 异步写审计日志（不阻塞响应）
    resource_type = _resolve_resource_type(path)
    action = _resolve_action(method, path)
    # 从路径提取 resource_id（简化：取最后一段若为 UUID）
    resource_id = None
    segments = [s for s in path.split("/") if s]
    if segments:
        last = segments[-1]
        try:
            uuid.UUID(last)
            resource_id = last
        except ValueError:
            pass

    try:
        async with async_session_maker() as db:
            await write_audit_log(
                db=db,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail={
                    "method": method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
                ip=ip,
                user_agent=ua,
            )
            await db.commit()
    except Exception as exc:
        # 审计日志失败不能影响业务
        logger.warning("审计日志写入失败 | path={} err={}", path, exc)

    return response
