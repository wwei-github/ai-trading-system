"""通用 Schema。

定义统一的 API 响应格式和分页响应格式。
"""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式。

    - code: 0 表示成功，非 0 表示错误
    - message: 响应消息
    - data: 响应数据
    """

    code: int = 0
    message: str = "ok"
    data: Optional[T] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应格式。"""

    total: int
    page: int
    page_size: int
    items: List[T]


class PaginationParams(BaseModel):
    """分页查询参数。"""

    page: int = 1
    page_size: int = 20


def success(data: Optional[T] = None, message: str = "ok") -> dict:
    """快速构造成功响应字典。"""
    return {"code": 0, "message": message, "data": data}
