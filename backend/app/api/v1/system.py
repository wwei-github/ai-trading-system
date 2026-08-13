"""系统管理接口。"""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import ApiResponse

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
        }
    )
