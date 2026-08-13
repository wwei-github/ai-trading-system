"""交易记录接口。"""

from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/trades", tags=["交易记录"])


@router.get("/health", summary="健康检查")
async def health_check():
    """交易记录模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "trades"})
