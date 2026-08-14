"""错误日志 Schema。"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorLogResponse(BaseModel):
    """错误日志响应。"""

    id: UUID
    request_id: Optional[str] = None
    level: str
    module: str
    message: str
    exception_type: Optional[str] = None
    traceback: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    request_params: Optional[Any] = None
    status_code: Optional[int] = None
    user_id: Optional[UUID] = None
    user_ip: Optional[str] = None
    user_agent: Optional[str] = None
    duration_ms: Optional[float] = None
    detail: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorLogListParams(BaseModel):
    """错误日志列表查询参数。"""

    level: Optional[str] = Field(None, description="筛选：ERROR / WARNING / INFO")
    module: Optional[str] = None
    status_code: Optional[int] = None
    keyword: Optional[str] = Field(
        None, description="搜索关键词（匹配 message 和 exception_type）"
    )
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ErrorLogStats(BaseModel):
    """错误日志统计。"""

    total_errors: int
    error_count: int
    warning_count: int
    info_count: int
    module_distribution: Dict[str, int]
    recent_errors: List[ErrorLogResponse]


class ErrorLogCleanRequest(BaseModel):
    """清理请求。"""

    before_days: int = Field(
        default=30, ge=1, le=365, description="清理 N 天前的日志"
    )
    level: Optional[str] = Field(None, description="仅清理指定级别")