"""路由依赖。

提供数据库会话、当前用户、分页参数等公共依赖。

鉴权策略（Stage 1）：
- 优先从 Authorization Bearer 解析 JWT → 加载用户
- 若未提供 token 且配置允许无鉴权模式（AUTH_FALLBACK_DEFAULT_USER=true），
  则回退到默认用户（便于本地无前端登录场景使用）
- 否则抛 401
"""

import uuid
from typing import Optional

from fastapi import Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_token
from app.models.user import User
from app.schemas.common import PaginationParams

# 默认开启回退：兼容现有前端无登录场景；生产环境应设为 false
AUTH_FALLBACK_DEFAULT_USER = True

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> User:
    """获取当前用户。

    优先 JWT；未提供 token 且 AUTH_FALLBACK_DEFAULT_USER=true 时回退默认用户。
    """
    if credentials is not None and credentials.credentials:
        try:
            payload = decode_token(credentials.credentials)
        except Exception:
            raise UnauthorizedException("Token 无效或已过期")
        if payload.get("type") != "access":
            raise UnauthorizedException("Token 类型错误")
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise UnauthorizedException("Token 缺少 sub")
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise UnauthorizedException("Token sub 非法")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise UnauthorizedException("用户不存在")
        if not user.is_active:
            raise UnauthorizedException("用户已停用")
        return user

    # 回退默认用户
    if AUTH_FALLBACK_DEFAULT_USER:
        user_id = uuid.UUID(settings.DEFAULT_USER_ID)
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            # 启动时未补齐时再补一次
            user = User(
                id=user_id,
                email=settings.DEFAULT_USER_EMAIL,
                hashed_password="",
                nickname=settings.DEFAULT_USER_NICKNAME,
                is_active=True,
                role="admin",
            )
            db.add(user)
            await db.flush()
        return user

    raise UnauthorizedException("未提供认证信息")


def get_pagination(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数，最大 100"),
) -> PaginationParams:
    """分页参数依赖。"""
    return PaginationParams(page=page, page_size=page_size)


__all__ = ["get_db", "get_current_user", "get_pagination", "AsyncSession"]
