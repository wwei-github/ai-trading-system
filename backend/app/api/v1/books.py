"""书籍接口。"""

from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/books", tags=["书籍管理"])


@router.get("/health", summary="健康检查")
async def health_check():
    """书籍模块健康检查。"""
    return ApiResponse(data={"status": "ok", "module": "books"})
