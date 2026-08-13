"""交易所账号接口。"""

from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/accounts", tags=["交易所账号"])


@router.get("/health", summary="健康检查")
async def health_check():
    """账号模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "accounts"})
