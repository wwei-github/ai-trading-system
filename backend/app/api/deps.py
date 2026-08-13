"""路由依赖。

提供数据库会话、当前用户、分页参数等公共依赖。

本项目当前不包含登录/认证流程，所有请求归属于一个默认用户
（通过 DEFAULT_USER_ID 配置）。后续接入认证时，只需替换
get_current_user 的实现即可。
"""

import uuid
from typing import Optional

from fastapi import Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginationParams


async def get_current_user(
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前用户。

    本项目无认证流程，统一返回默认用户。若默认用户不存在则创建。
    """
    user_id = uuid.UUID(settings.DEFAULT_USER_ID)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            id=user_id,
            email=settings.DEFAULT_USER_EMAIL,
            hashed_password="",  # 无认证，留空
            nickname=settings.DEFAULT_USER_NICKNAME,
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.flush()

    return user


def get_pagination(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数，最大 100"),
) -> PaginationParams:
    """分页参数依赖。"""
    return PaginationParams(page=page, page_size=page_size)


__all__ = ["get_db", "get_current_user", "get_pagination", "AsyncSession"]
