"""限流器（slowapi）。

仅当 settings.RATE_LIMIT_ENABLED=true 时生效，否则所有装饰器为 no-op。
"""

from typing import Optional

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.exceptions import RateLimitException


def _enabled() -> bool:
    return bool(settings.RATE_LIMIT_ENABLED)


# 当未启用限流时，key_func 返回 None → slowapi 会跳过
def _key_func(request: Request) -> Optional[str]:
    if not _enabled():
        return None
    # 已登录用户用 user.id，否则用 IP
    user = getattr(request.state, "user", None)
    if user is not None and getattr(user, "id", None) is not None:
        return f"user:{user.id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_key, enabled=_enabled())


def rate_limit(per_minute: int):
    """装饰器：每分钟 per_minute 次。

    用法：
        @router.post("/login")
        @rate_limit(settings.RATE_LIMIT_LOGIN_PER_MIN)
        async def login(...): ...
    """
    if not _enabled():
        # 未启用限流：返回一个什么都不做的装饰器
        def _noop(func):
            return func
        return _noop
    return limiter.limit(f"{per_minute}/minute")


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """限流异常 → 转换为项目统一错误格式。"""
    detail = getattr(exc, "detail", "Rate limit exceeded")
    retry_after = getattr(exc, "retry_after", None)
    raise RateLimitException(
        message="请求过于频繁，请稍后再试",
        detail={"retry_after": retry_after, "limit": detail},
    )
