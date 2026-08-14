"""系统管理接口。"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_pagination
from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.permissions import require_roles
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from app.schemas.system import (
    AuditLogResponse,
    NotificationSettings,
    SystemConfigItemCreate,
    SystemConfigItemResponse,
    SystemConfigItemUpdate,
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


@router.get("/config", summary="获取系统配置", dependencies=[Depends(require_roles("admin"))])
async def get_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取系统配置。"""
    service = SystemService(db)
    return ApiResponse(data=service.get_system_config())


@router.patch("/config", summary="更新系统配置", dependencies=[Depends(require_roles("admin"))])
async def update_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新系统配置（当前运行时配置通过环境变量管理，此接口预留）。"""
    service = SystemService(db)
    return ApiResponse(data=service.get_system_config())


# ---------- 系统配置 CRUD（持久化到 system_configs 表） ----------


@router.get(
    "/configs",
    summary="获取系统配置项列表",
    dependencies=[Depends(require_roles("admin"))],
)
async def list_config_items(
    category: Optional[str] = Query(
        None, description="按分类筛选：ai/exchanges/risk/notifications/storage"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取系统配置项列表，可按分类筛选。"""
    service = SystemService(db)
    items = await service.list_config_items(category=category)
    return ApiResponse(
        data=[SystemConfigItemResponse.model_validate(i) for i in items]
    )


@router.post(
    "/configs",
    summary="创建/更新系统配置项",
    status_code=201,
    dependencies=[Depends(require_roles("admin"))],
)
async def upsert_config_item(
    data: SystemConfigItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建或更新系统配置项（基于 category + key 唯一约束，存在则更新）。"""
    service = SystemService(db)
    item = await service.upsert_config_item(data)
    return ApiResponse(data=SystemConfigItemResponse.model_validate(item))


@router.get(
    "/configs/{category}/{key}",
    summary="获取单个系统配置项",
    dependencies=[Depends(require_roles("admin"))],
)
async def get_config_item(
    category: str,
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定分类和键的配置项。"""
    service = SystemService(db)
    item = await service.get_config_item(category, key)
    if item is None:
        raise NotFoundException(
            message="配置项不存在",
            detail={"category": category, "key": key},
        )
    return ApiResponse(data=SystemConfigItemResponse.model_validate(item))


@router.patch(
    "/configs/{category}/{key}",
    summary="更新系统配置项",
    dependencies=[Depends(require_roles("admin"))],
)
async def update_config_item(
    category: str,
    key: str,
    data: SystemConfigItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新指定配置项的 value 和 description。"""
    service = SystemService(db)
    item = await service.update_config_item(category, key, data)
    if item is None:
        raise NotFoundException(
            message="配置项不存在",
            detail={"category": category, "key": key},
        )
    return ApiResponse(data=SystemConfigItemResponse.model_validate(item))


@router.delete(
    "/configs/{category}/{key}",
    summary="删除系统配置项",
    dependencies=[Depends(require_roles("admin"))],
)
async def delete_config_item(
    category: str,
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除指定配置项。"""
    service = SystemService(db)
    deleted = await service.delete_config_item(category, key)
    if not deleted:
        raise NotFoundException(
            message="配置项不存在",
            detail={"category": category, "key": key},
        )
    return ApiResponse(data={"deleted": True})


# ---------- AI Provider 管理（独立路由，区分新建和编辑） ----------


@router.post(
    "/configs/ai",
    summary="新建 AI Provider",
    status_code=201,
    dependencies=[Depends(require_roles("admin"))],
)
async def create_ai_provider(
    data: SystemConfigItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新的 AI Provider 配置。"""
    service = SystemService(db)
    if data.category != "ai":
        raise BadRequestException(message="AI Provider 配置分类必须为 ai")
    result = await service.create_config(data)
    return ApiResponse(data=result)


@router.put(
    "/configs/ai/{config_id}",
    summary="编辑 AI Provider",
    dependencies=[Depends(require_roles("admin"))],
)
async def update_ai_provider(
    config_id: uuid.UUID,
    data: SystemConfigItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新已有 AI Provider 配置。"""
    service = SystemService(db)
    result = await service.update_config(config_id, data)
    return ApiResponse(data=result)


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


@router.get("/audit-logs", summary="获取审计日志", dependencies=[Depends(require_roles("admin"))])
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


@router.get(
    "/audit-logs/export",
    summary="导出审计日志为 CSV",
    dependencies=[Depends(require_roles("admin"))],
)
async def export_audit_logs(
    user_id: uuid.UUID = Query(None, description="按用户筛选"),
    action: str = Query(None, description="按动作筛选"),
    resource_type: str = Query(None, description="按资源类型筛选"),
    start_time: datetime = Query(None, description="起始时间（ISO 8601）"),
    end_time: datetime = Query(None, description="结束时间（ISO 8601）"),
    limit: int = Query(10000, ge=1, le=50000, description="导出条数上限"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出审计日志为 CSV 文件（支持筛选，最多 50000 条）。"""
    service = SystemService(db)
    csv_content = await service.export_audit_logs_csv(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    filename = f"audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
