"""系统管理服务。

处理用户管理、系统配置、通知设置、审计日志查询。
"""

import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.system import (
    AuditLogResponse,
    NotificationSettings,
    SystemConfigResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)


class SystemService:
    """系统管理服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- 用户管理 ----------

    async def list_users(
        self, params: PaginationParams
    ) -> Tuple[List[User], int]:
        """获取用户列表（分页）。"""
        # 总数
        count_result = await self.db.execute(select(func.count(User.id)))
        total = count_result.scalar_one()

        # 分页查询
        offset = (params.page - 1) * params.page_size
        result = await self.db.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        )
        return list(result.scalars().all()), total

    async def get_user(self, user_id: uuid.UUID) -> Optional[User]:
        """获取用户详情。"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, data: UserCreate) -> User:
        """创建用户。"""
        user = User(
            email=data.email,
            hashed_password="",  # 无认证流程
            nickname=data.nickname,
            role=data.role,
            is_active=data.is_active,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def update_user(
        self, user_id: uuid.UUID, data: UserUpdate
    ) -> Optional[User]:
        """更新用户信息。"""
        user = await self.get_user(user_id)
        if user is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)
        await self.db.flush()
        return user

    # ---------- 系统配置 ----------

    def get_system_config(self) -> SystemConfigResponse:
        """获取系统配置。"""
        return SystemConfigResponse(
            app_name=settings.APP_NAME,
            app_env=settings.APP_ENV,
            api_prefix=settings.API_PREFIX,
            debug=settings.DEBUG,
            llm_provider=settings.LLM_PROVIDER,
            llm_model=settings.LLM_MODEL,
        )

    # ---------- 通知设置（当前为内存默认值，可扩展为持久化） ----------

    def get_notification_settings(self) -> NotificationSettings:
        """获取通知设置。"""
        return NotificationSettings()

    def update_notification_settings(
        self, data: NotificationSettings
    ) -> NotificationSettings:
        """更新通知设置。"""
        # TODO: 持久化到数据库或配置文件
        return data

    # ---------- 审计日志 ----------

    async def list_audit_logs(
        self,
        params: PaginationParams,
        user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> Tuple[List[AuditLog], int]:
        """获取审计日志列表（分页 + 筛选）。"""
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
            count_query = count_query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
            count_query = count_query.where(
                AuditLog.resource_type == resource_type
            )

        total = (await self.db.execute(count_query)).scalar_one()
        offset = (params.page - 1) * params.page_size
        result = await self.db.execute(
            query.order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        )
        return list(result.scalars().all()), total
