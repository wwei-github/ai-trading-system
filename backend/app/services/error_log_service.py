"""错误日志服务。"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_log import ErrorLog
from app.schemas.error_log import ErrorLogResponse


class ErrorLogService:
    """错误日志服务。"""

    MODULES = {
        "api",
        "db",
        "exchange",
        "ai",
        "celery",
        "system",
        "auth",
        "account",
        "trade",
        "strategy",
        "book",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_error(
        self,
        level: str,
        module: str,
        message: str,
        request_id: Optional[str] = None,
        exception_type: Optional[str] = None,
        traceback: Optional[str] = None,
        request_path: Optional[str] = None,
        request_method: Optional[str] = None,
        request_params: Optional[Any] = None,
        status_code: Optional[int] = None,
        user_id: Optional[uuid.UUID] = None,
        user_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        duration_ms: Optional[float] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> ErrorLog:
        """写入一条错误日志。"""
        log = ErrorLog(
            request_id=request_id,
            level=level,
            module=module,
            message=str(message)[:1000],  # 截断过长的消息
            exception_type=exception_type,
            traceback=str(traceback)[:5000] if traceback else None,
            request_path=request_path,
            request_method=request_method,
            request_params=request_params,
            status_code=status_code,
            user_id=user_id,
            user_ip=user_ip,
            user_agent=user_agent,
            duration_ms=duration_ms,
            detail=detail,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_logs(
        self,
        level: Optional[str] = None,
        module: Optional[str] = None,
        status_code: Optional[int] = None,
        keyword: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ErrorLogResponse], int]:
        """分页查询错误日志。"""
        query = select(ErrorLog)
        count_query = select(func.count(ErrorLog.id))

        # 筛选条件
        conditions = []
        if level:
            conditions.append(ErrorLog.level == level.upper())
        if module:
            conditions.append(ErrorLog.module == module)
        if status_code:
            conditions.append(ErrorLog.status_code == status_code)
        if keyword:
            keyword_filter = text(
                "message ILIKE :kw OR exception_type ILIKE :kw"
            ).bindparams(kw=f"%{keyword}%")
            conditions.append(keyword_filter)
        if start_time:
            conditions.append(ErrorLog.created_at >= start_time)
        if end_time:
            conditions.append(ErrorLog.created_at <= end_time)

        for cond in conditions:
            query = query.where(cond)
            count_query = count_query.where(cond)

        # 总数
        total = (await self.db.execute(count_query)).scalar_one()

        # 分页
        query = (
            query.order_by(ErrorLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        return (
            [ErrorLogResponse.model_validate(l) for l in logs],
            total,
        )

    async def get_log(self, log_id: uuid.UUID) -> Optional[ErrorLogResponse]:
        """获取单条错误日志详情。"""
        result = await self.db.execute(
            select(ErrorLog).where(ErrorLog.id == log_id)
        )
        log = result.scalar_one_or_none()
        if log is None:
            return None
        return ErrorLogResponse.model_validate(log)

    async def get_stats(self) -> Dict[str, Any]:
        """获取错误日志统计。"""
        # 总数
        total = (
            await self.db.execute(select(func.count(ErrorLog.id)))
        ).scalar_one()

        # 按级别统计
        level_counts = await self.db.execute(
            select(ErrorLog.level, func.count(ErrorLog.id)).group_by(ErrorLog.level)
        )
        level_map = dict(level_counts.all())

        # 按模块统计
        module_counts = await self.db.execute(
            select(ErrorLog.module, func.count(ErrorLog.id))
            .group_by(ErrorLog.module)
            .order_by(func.count(ErrorLog.id).desc())
            .limit(10)
        )
        module_dist = dict(module_counts.all())

        # 最近 5 条错误
        recent = await self.db.execute(
            select(ErrorLog)
            .where(ErrorLog.level == "ERROR")
            .order_by(ErrorLog.created_at.desc())
            .limit(5)
        )
        recent_logs = [
            ErrorLogResponse.model_validate(l) for l in recent.scalars().all()
        ]

        return {
            "total_errors": total,
            "error_count": level_map.get("ERROR", 0),
            "warning_count": level_map.get("WARNING", 0),
            "info_count": level_map.get("INFO", 0),
            "module_distribution": module_dist,
            "recent_errors": recent_logs,
        }

    async def clean_old_logs(
        self, before_days: int = 30, level: Optional[str] = None
    ) -> int:
        """清理旧日志。"""
        cutoff = datetime.utcnow() - timedelta(days=before_days)
        query = delete(ErrorLog).where(ErrorLog.created_at < cutoff)
        if level:
            query = query.where(ErrorLog.level == level.upper())
        result = await self.db.execute(query)
        await self.db.flush()
        return result.rowcount