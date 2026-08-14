"""错误日志模型。"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ErrorLog(Base):
    """错误日志表。

    记录系统异常、4xx/5xx 响应等错误信息，支持分级存储和查询。
    """

    __tablename__ = "error_logs"

    request_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    exception_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    request_params: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    detail: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)