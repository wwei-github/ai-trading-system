"""币种分析接口。"""

from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/coins", tags=["币种分析"])


@router.get("/health", summary="健康检查")
async def health_check():
    """币种分析模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "coins"})
