"""用户管理 API。

- GET    /users/me           本人资料
- PATCH  /users/me           本人更新资料
- GET    /users              Admin 用户列表
- PATCH  /users/{id}         Admin 更新用户
- POST   /users/{id}/reset-password  Admin 重置密码
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.core.permissions import require_roles
from app.core.security import hash_password
from app.models.user import User
from app.schemas.common import success
from app.schemas.users import (
    AdminResetPasswordRequest,
    UserAdminUpdateRequest,
    UserListItem,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("/me", response_model=dict, summary="当前用户资料")
async def get_me(current_user: User = Depends(get_current_user)):
    return success(UserListItem.model_validate(current_user).model_dump(mode="json"))


@router.patch("/me", response_model=dict, summary="更新本人资料")
async def update_me(
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.nickname is not None:
        current_user.nickname = data.nickname
    if data.email is not None and data.email != current_user.email:
        # 邮箱变更需要重新验证
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none() is not None:
            raise BadRequestException("邮箱已被使用")
        current_user.email = data.email
        current_user.email_verified = False
    await db.commit()
    return success(UserListItem.model_validate(current_user).model_dump(mode="json"))


@router.get(
    "",
    response_model=dict,
    summary="用户列表（Admin）",
    dependencies=[Depends(require_roles("admin"))],
)
async def list_users(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    users = result.scalars().all()
    items = [UserListItem.model_validate(u).model_dump(mode="json") for u in users]
    return success({"items": items, "page": page, "page_size": page_size, "total": len(items)})


@router.patch(
    "/{user_id}",
    response_model=dict,
    summary="Admin 更新用户",
    dependencies=[Depends(require_roles("admin"))],
)
async def admin_update_user(
    user_id: str,
    data: UserAdminUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise BadRequestException("user_id 非法")
    user = await db.get(User, uid)
    if user is None:
        raise NotFoundException("用户不存在")

    if data.nickname is not None:
        user.nickname = data.nickname
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.email_verified is not None:
        user.email_verified = data.email_verified
    await db.commit()
    return success(UserListItem.model_validate(user).model_dump(mode="json"))


@router.post(
    "/{user_id}/reset-password",
    response_model=dict,
    summary="Admin 重置密码",
    dependencies=[Depends(require_roles("admin"))],
)
async def admin_reset_password(
    user_id: str,
    data: AdminResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise BadRequestException("user_id 非法")
    user = await db.get(User, uid)
    if user is None:
        raise NotFoundException("用户不存在")
    user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return success(None, "密码已重置")
