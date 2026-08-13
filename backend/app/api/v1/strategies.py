"""策略接口。"""

from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/strategies", tags=["策略管理"])


@router.get("/health", summary="健康检查")
async def health_check():
    """策略模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "strategies"})
