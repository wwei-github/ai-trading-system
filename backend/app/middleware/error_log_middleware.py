"""错误日志中间件。

捕获所有请求的异常和 4xx/5xx 响应，写入 error_logs 表。
与现有 audit_middleware 互补：audit 记录用户操作，error_log 记录系统错误。
"""

import json
import time
import uuid
from typing import Optional

from fastapi import Request, Response
from loguru import logger

from app.core.database import async_session_maker
from app.core.security import decode_token
from app.services.error_log_service import ErrorLogService

# 不记录的路径
EXCLUDE_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}
EXCLUDE_PREFIXES = ("/docs/", "/openapi/", "/redoc/", "/health")

# 日志级别配置
ERROR_STATUS_CODES = {500, 502, 503, 504}
WARNING_STATUS_CODES = {400, 401, 403, 404, 409, 422, 429}


def _generate_request_id() -> str:
    """生成唯一请求追踪 ID。"""
    return uuid.uuid4().hex[:16]


def _resolve_module(path: str) -> str:
    """从请求路径解析模块名。"""
    path = path.lstrip("/")
    parts = path.split("/")
    # /api/v1/{module}/...
    if len(parts) >= 3 and parts[0] == "api":
        return parts[2]
    return "system"


def _resolve_user_id(request: Request) -> Optional[str]:
    """从 Authorization 头解析 user_id。"""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload["sub"]
    except Exception:
        return None


async def _try_get_request_body(request: Request) -> Optional[dict]:
    """尝试获取请求体（仅记录时使用，不影响业务）。"""
    if request.method in ("GET", "HEAD"):
        return None
    try:
        body = await request.body()
        if body:
            # 限制大小，避免大文件上传
            if len(body) > 1024 * 100:
                return {"_truncated": True, "size": len(body)}
            return json.loads(body)
    except Exception:
        return None
    return None


async def error_log_middleware(request: Request, call_next) -> Response:
    """错误日志中间件。

    职责：
    1. 注入 request_id 到 request.state
    2. 捕获所有异常，写入 error_logs 表
    3. 记录 4xx/5xx 响应
    4. 不阻塞业务请求
    """

    # 跳过排除路径
    path = request.url.path
    if path in EXCLUDE_PATHS or path.startswith(EXCLUDE_PREFIXES):
        return await call_next(request)

    # 生成 request_id
    request_id = _generate_request_id()
    request.state.request_id = request_id

    method = request.method
    module = _resolve_module(path)
    user_id = _resolve_user_id(request)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:200]

    start = time.time()
    status_code = 200
    error = None
    traceback_str = None
    exception_type = None
    request_params = None

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as e:
        status_code = 500
        error = str(e)
        exception_type = type(e).__name__
        import traceback

        traceback_str = traceback.format_exc()
        # 重新抛出异常，让全局异常处理器处理
        raise
    finally:
        duration_ms = (time.time() - start) * 1000

        # 决定日志级别
        level = None
        if error or status_code in ERROR_STATUS_CODES:
            level = "ERROR"
        elif status_code in WARNING_STATUS_CODES:
            level = "WARNING"

        if level is None:
            return

        # 获取请求参数
        try:
            if request.method == "GET":
                request_params = dict(request.query_params)
            else:
                request_params = await _try_get_request_body(request)
        except Exception:
            pass

        # 异步写入数据库
        try:
            async with async_session_maker() as db:
                service = ErrorLogService(db)
                await service.log_error(
                    level=level,
                    module=module,
                    message=error or f"HTTP {status_code}",
                    request_id=request_id,
                    exception_type=exception_type,
                    traceback=traceback_str,
                    request_path=path,
                    request_method=method,
                    request_params=request_params,
                    status_code=status_code,
                    user_id=user_id,
                    user_ip=ip,
                    user_agent=ua,
                    duration_ms=round(duration_ms, 2),
                    detail={
                        "headers": {
                            k: v
                            for k, v in request.headers.items()
                            if k.lower() not in ("authorization", "cookie")
                        },
                    },
                )
                await db.commit()
        except Exception as log_err:
            logger.warning(f"写入错误日志失败: {log_err}")