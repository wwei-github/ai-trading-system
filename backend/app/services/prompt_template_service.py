"""Prompt 模板服务层。"""

import logging
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
)

logger = logging.getLogger(__name__)


class PromptTemplateService:
    """Prompt 模板 CRUD 业务。"""

    CATEGORIES = ("initial_analysis", "backtest_precheck", "deep_analysis")

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_templates(
        self, category: Optional[str] = None, active_only: bool = False
    ) -> Tuple[List[PromptTemplateResponse], int]:
        """获取模板列表。"""
        query = select(PromptTemplate).order_by(PromptTemplate.created_at.desc())
        if category:
            query = query.where(PromptTemplate.category == category)
        if active_only:
            query = query.where(PromptTemplate.is_active == True)

        result = await self.db.execute(query)
        templates = result.scalars().all()
        return (
            [PromptTemplateResponse.model_validate(t) for t in templates],
            len(templates),
        )

    async def get_template(self, template_id: UUID) -> PromptTemplateResponse:
        """获取模板详情。"""
        template = await self.db.get(PromptTemplate, template_id)
        if not template:
            raise NotFoundException(message=f"Prompt 模板不存在: {template_id}")
        return PromptTemplateResponse.model_validate(template)

    async def create_template(self, data: PromptTemplateCreate) -> PromptTemplateResponse:
        """创建模板。"""
        template = PromptTemplate(
            category=data.category,
            name=data.name,
            content=data.content,
            is_active=data.is_active,
            version=1,
        )
        self.db.add(template)
        await self.db.flush()
        logger.info(f"Prompt template created: {template.id} ({data.category})")
        return PromptTemplateResponse.model_validate(template)

    async def update_template(
        self, template_id: UUID, data: PromptTemplateUpdate
    ) -> PromptTemplateResponse:
        """更新模板（版本号 +1）。"""
        template = await self.db.get(PromptTemplate, template_id)
        if not template:
            raise NotFoundException(message=f"Prompt 模板不存在: {template_id}")

        update_data = data.model_dump(exclude_unset=True)
        if update_data:
            update_data["version"] = template.version + 1
            stmt = (
                update(PromptTemplate)
                .where(PromptTemplate.id == template_id)
                .values(**update_data)
            )
            await self.db.execute(stmt)
            await self.db.flush()

        # 重新读取
        updated = await self.db.get(PromptTemplate, template_id)
        return PromptTemplateResponse.model_validate(updated)

    async def delete_template(self, template_id: UUID) -> None:
        """删除模板。"""
        template = await self.db.get(PromptTemplate, template_id)
        if not template:
            raise NotFoundException(message=f"Prompt 模板不存在: {template_id}")
        await self.db.delete(template)
        await self.db.flush()