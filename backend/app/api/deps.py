"""路由依赖。

提供数据库会话等公共依赖。本项目不包含认证，无认证相关依赖。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

__all__ = ["get_db", "AsyncSession"]
