"""错误日志 API 路由。"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.error_log import ErrorLogCleanRequest, ErrorLogResponse, ErrorLogStats
from app.services.error_log_service import ErrorLogService

router = APIRouter(prefix="/system/error-logs", tags=["系统管理 - 错误日志"])


@router.get("", summary="获取错误日志列表")
async def list_error_logs(
    level: Optional[str] = Query(None, description="筛选：ERROR / WARNING / INFO"),
    module: Optional[str] = Query(None, description="模块名"),
    status_code: Optional[int] = Query(None, description="HTTP 状态码"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页查询错误日志，支持按级别/模块/状态码/关键词/时间范围筛选。"""
    service = ErrorLogService(db)
    logs, total = await service.list_logs(
        level=level,
        module=module,
        status_code=status_code,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=PaginatedResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=logs,
        )
    )


@router.get("/{log_id}", summary="获取错误日志详情")
async def get_error_log(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单条错误日志的完整信息（含异常栈）。"""
    service = ErrorLogService(db)
    log = await service.get_log(log_id)
    if log is None:
        raise NotFoundException(message="错误日志不存在")
    return ApiResponse(data=log)


@router.get("/stats", summary="获取错误日志统计")
async def get_error_log_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取错误日志统计信息（总数、级别分布、模块分布）。"""
    service = ErrorLogService(db)
    stats = await service.get_stats()
    return ApiResponse(data=stats)


@router.post("/clean", summary="清理历史错误日志")
async def clean_error_logs(
    data: ErrorLogCleanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清理指定天数前的旧日志。"""
    service = ErrorLogService(db)
    deleted = await service.clean_old_logs(
        before_days=data.before_days, level=data.level
    )
    return ApiResponse(data={"deleted_count": deleted})