"""错误日志工具函数，供业务代码主动调用。"""

import uuid
from typing import Any, Dict, Optional

from app.core.database import async_session_maker
from app.services.error_log_service import ErrorLogService


async def log_error(
    level: str,
    module: str,
    message: str,
    request_id: Optional[str] = None,
    exception_type: Optional[str] = None,
    traceback: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    **kwargs,
):
    """主动写入错误日志（供业务代码调用）。"""
    try:
        async with async_session_maker() as db:
            service = ErrorLogService(db)
            await service.log_error(
                level=level,
                module=module,
                message=message,
                request_id=request_id,
                exception_type=exception_type,
                traceback=traceback,
                detail=detail,
                **kwargs,
            )
            await db.commit()
    except Exception as e:
        from loguru import logger

        logger.warning(f"写入错误日志失败: {e}")