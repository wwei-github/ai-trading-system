"""系统管理接口。"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_pagination
from app.core.config import settings
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.system import (
    AuditLogResponse,
    NotificationSettings,
    SystemConfigResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.system_service import SystemService

router = APIRouter(prefix="/system", tags=["系统管理"])


@router.get("/health", summary="健康检查")
async def health_check():
    """系统模块健康检查。"""
    return ApiResponse(
        data={
            "status": "ok",
            "module": "system",
            "app_env": settings.APP_ENV,
            "debug": settings.DEBUG,
        }
    )


@router.get("/info", summary="系统信息")
async def system_info():
    """获取系统信息。"""
    return ApiResponse(
        data={
            "app_name": settings.APP_NAME,
            "app_env": settings.APP_ENV,
            "api_prefix": settings.API_PREFIX,
            "version": "1.0.0",
        }
    )


# ---------- 用户管理 ----------


@router.get("/users", summary="获取用户列表")
async def list_users(
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户列表（分页）。"""
    service = SystemService(db)
    users, total = await service.list_users(pagination)
    return ApiResponse(
        data=PaginatedResponse(
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            items=[UserResponse.model_validate(u) for u in users],
        )
    )


@router.post("/users", summary="创建用户")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建用户。"""
    service = SystemService(db)
    user = await service.create_user(data)
    return ApiResponse(data=UserResponse.model_validate(user))


@router.patch("/users/{user_id}", summary="更新用户")
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新用户信息。"""
    service = SystemService(db)
    user = await service.update_user(user_id, data)
    if user is None:
        return ApiResponse(code=404, message="用户不存在", data=None)
    return ApiResponse(data=UserResponse.model_validate(user))


# ---------- 系统配置 ----------


@router.get("/config", summary="获取系统配置")
async def get_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取系统配置。"""
    service = SystemService(db)
    return ApiResponse(data=service.get_system_config())


@router.patch("/config", summary="更新系统配置")
async def update_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新系统配置（当前运行时配置通过环境变量管理，此接口预留）。"""
    service = SystemService(db)
    return ApiResponse(data=service.get_system_config())


# ---------- 通知设置 ----------


@router.get("/notifications", summary="获取通知设置")
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取通知设置。"""
    service = SystemService(db)
    return ApiResponse(data=service.get_notification_settings())


@router.patch("/notifications", summary="更新通知设置")
async def update_notifications(
    data: NotificationSettings,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新通知设置。"""
    service = SystemService(db)
    return ApiResponse(data=service.update_notification_settings(data))


# ---------- 审计日志 ----------


@router.get("/audit-logs", summary="获取审计日志")
async def list_audit_logs(
    pagination: PaginationParams = Depends(get_pagination),
    user_id: uuid.UUID = Query(None, description="按用户筛选"),
    action: str = Query(None, description="按动作筛选"),
    resource_type: str = Query(None, description="按资源类型筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审计日志列表（分页 + 筛选）。"""
    service = SystemService(db)
    logs, total = await service.list_audit_logs(
        pagination,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
    )
    return ApiResponse(
        data=PaginatedResponse(
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            items=[AuditLogResponse.model_validate(log) for log in logs],
        )
    )
