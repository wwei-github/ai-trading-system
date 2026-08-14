"""系统管理服务。

处理用户管理、系统配置、通知设置、审计日志查询。
系统配置持久化到 system_configs 表，支持分类管理。
审计日志支持 CSV 导出。
"""

import csv
import io
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.audit import AuditLog
from app.models.system_config import SystemConfig
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.system import (
    AuditLogResponse,
    NotificationSettings,
    SystemConfigItemCreate,
    SystemConfigItemResponse,
    SystemConfigItemUpdate,
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

    async def export_audit_logs_csv(
        self,
        user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 10000,
    ) -> str:
        """导出审计日志为 CSV 字符串。

        支持按用户、动作、资源类型、时间范围筛选，最多导出 limit 条。
        """
        query = select(AuditLog)
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if start_time:
            query = query.where(AuditLog.created_at >= start_time)
        if end_time:
            query = query.where(AuditLog.created_at <= end_time)
        query = query.order_by(AuditLog.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        # 关联用户邮箱（一次性查询，避免 N+1）
        user_ids = {log.user_id for log in logs if log.user_id}
        user_map: Dict[uuid.UUID, str] = {}
        if user_ids:
            users_result = await self.db.execute(
                select(User.id, User.email).where(User.id.in_(user_ids))
            )
            user_map = {row[0]: row[1] for row in users_result.all()}

        output = io.StringIO()
        # 加入 BOM 以便 Excel 正确识别 UTF-8
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow(
            [
                "ID",
                "时间",
                "用户ID",
                "用户邮箱",
                "动作",
                "资源类型",
                "资源ID",
                "IP地址",
                "操作详情",
            ]
        )
        for log in logs:
            writer.writerow(
                [
                    str(log.id),
                    log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    str(log.user_id) if log.user_id else "",
                    user_map.get(log.user_id, "") if log.user_id else "",
                    log.action,
                    log.resource_type or "",
                    log.resource_id or "",
                    log.ip or "",
                    str(log.detail) if log.detail else "",
                ]
            )
        return output.getvalue()

    # ---------- 系统配置 CRUD（持久化） ----------

    async def list_config_items(
        self, category: Optional[str] = None
    ) -> List[SystemConfig]:
        """获取系统配置项列表，可按分类筛选。"""
        stmt = select(SystemConfig).order_by(
            SystemConfig.category.asc(), SystemConfig.key.asc()
        )
        if category:
            stmt = stmt.where(SystemConfig.category == category)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_config_item(
        self, category: str, key: str
    ) -> Optional[SystemConfig]:
        """获取单个配置项。"""
        result = await self.db.execute(
            select(SystemConfig).where(
                SystemConfig.category == category,
                SystemConfig.key == key,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_config_item(
        self, data: SystemConfigItemCreate
    ) -> SystemConfig:
        """创建或更新配置项（基于 category + key 唯一约束）。"""
        existing = await self.get_config_item(data.category, data.key)
        if existing is not None:
            existing.value = data.value
            if data.description is not None:
                existing.description = data.description
            await self.db.flush()
            return existing

        item = SystemConfig(
            category=data.category,
            key=data.key,
            value=data.value,
            description=data.description,
        )
        self.db.add(item)
        await self.db.flush()
        return item

    async def update_config_item(
        self,
        category: str,
        key: str,
        data: SystemConfigItemUpdate,
    ) -> Optional[SystemConfig]:
        """更新配置项的 value 和 description。"""
        item = await self.get_config_item(category, key)
        if item is None:
            return None
        item.value = data.value
        if data.description is not None:
            item.description = data.description
        await self.db.flush()
        return item

    async def delete_config_item(
        self, category: str, key: str
    ) -> bool:
        """删除配置项。"""
        item = await self.get_config_item(category, key)
        if item is None:
            return False
        await self.db.delete(item)
        await self.db.flush()
        return True

    async def create_config(self, data: SystemConfigItemCreate) -> SystemConfigItemResponse:
        """创建系统配置项（新建模式）。"""
        config = SystemConfig(
            category=data.category,
            key=data.key,
            value=data.value,
            description=data.description,
        )
        self.db.add(config)
        await self.db.flush()
        return SystemConfigItemResponse.model_validate(config)

    async def update_config(
        self, config_id: uuid.UUID, data: SystemConfigItemUpdate
    ) -> SystemConfigItemResponse:
        """更新系统配置项（使用 ID 定位）。"""
        result = await self.db.execute(
            select(SystemConfig).where(SystemConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            raise NotFoundException(message="配置项不存在")
        config.value = data.value
        if data.description is not None:
            config.description = data.description
        await self.db.flush()
        return SystemConfigItemResponse.model_validate(config)
