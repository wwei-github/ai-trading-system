"""交易标签服务。

支持标签 CRUD + 颜色 + 合并操作。
合并时将源标签从所有交易记录的 tags 数组中替换为目标标签，
并删除源标签。
"""

import uuid
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.trade import Trade
from app.models.trade_tag import TradeTag
from app.schemas.trade_tag import TradeTagCreate, TradeTagUpdate


class TradeTagService:
    """交易标签服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tag(
        self, user_id: uuid.UUID, data: TradeTagCreate
    ) -> TradeTag:
        """创建标签（user_id + name 唯一）。"""
        # 唯一性检查
        existing = await self.db.execute(
            select(TradeTag).where(
                TradeTag.user_id == user_id,
                TradeTag.name == data.name,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise BadRequestException(
                f"标签 '{data.name}' 已存在",
                detail={"name": data.name},
            )

        tag = TradeTag(
            user_id=user_id,
            name=data.name,
            color=data.color,
        )
        self.db.add(tag)
        await self.db.flush()
        await self.db.refresh(tag)
        return tag

    async def list_tags(
        self, user_id: uuid.UUID
    ) -> List[TradeTag]:
        """获取用户全部标签（按使用次数降序）。"""
        result = await self.db.execute(
            select(TradeTag)
            .where(TradeTag.user_id == user_id)
            .order_by(TradeTag.usage_count.desc(), TradeTag.name.asc())
        )
        return list(result.scalars().all())

    async def get_tag(
        self, tag_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[TradeTag]:
        """获取单个标签。"""
        result = await self.db.execute(
            select(TradeTag).where(
                TradeTag.id == tag_id,
                TradeTag.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_tag(
        self, tag_id: uuid.UUID, user_id: uuid.UUID, data: TradeTagUpdate
    ) -> Optional[TradeTag]:
        """更新标签。"""
        tag = await self.get_tag(tag_id, user_id)
        if tag is None:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # 名称变更时检查唯一性
        if "name" in update_data and update_data["name"] != tag.name:
            existing = await self.db.execute(
                select(TradeTag).where(
                    TradeTag.user_id == user_id,
                    TradeTag.name == update_data["name"],
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise BadRequestException(
                    f"标签 '{update_data['name']}' 已存在",
                    detail={"name": update_data["name"]},
                )

        for key, value in update_data.items():
            setattr(tag, key, value)

        await self.db.flush()
        await self.db.refresh(tag)
        return tag

    async def delete_tag(
        self, tag_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """删除标签。

        同时从所有引用该标签的交易记录的 tags 数组中移除。
        """
        tag = await self.get_tag(tag_id, user_id)
        if tag is None:
            return False

        tag_name = tag.name

        # 从所有交易记录的 tags 数组中移除该标签
        # PostgreSQL JSONB 操作：tags - 'value' 删除数组元素
        # SQLite 兼容：应用层处理
        trades_result = await self.db.execute(
            select(Trade).where(
                Trade.user_id == user_id,
                Trade.tags.op("@>")([tag_name]),
            )
        )
        trades = list(trades_result.scalars().all())
        for trade in trades:
            if trade.tags and tag_name in trade.tags:
                trade.tags = [t for t in trade.tags if t != tag_name]

        await self.db.delete(tag)
        await self.db.flush()
        return True

    async def merge_tags(
        self,
        user_id: uuid.UUID,
        source_tag_ids: List[uuid.UUID],
        target_tag_id: uuid.UUID,
    ) -> dict:
        """合并标签。

        将 source_tags 中所有标签替换为 target_tag：
        1. 遍历所有引用源标签的交易记录
        2. 将 tags 数组中的源标签名替换为目标标签名（去重）
        3. 删除源标签
        """
        if target_tag_id in source_tag_ids:
            raise BadRequestException("目标标签不能在源标签列表中")

        target_tag = await self.get_tag(target_tag_id, user_id)
        if target_tag is None:
            raise NotFoundException(
                "目标标签不存在", detail={"tag_id": str(target_tag_id)}
            )

        # 加载所有源标签
        source_tags: List[TradeTag] = []
        for sid in source_tag_ids:
            tag = await self.get_tag(sid, user_id)
            if tag is None:
                raise NotFoundException(
                    "源标签不存在", detail={"tag_id": str(sid)}
                )
            source_tags.append(tag)

        source_names = [t.name for t in source_tags]
        target_name = target_tag.name

        # 查询所有引用任一源标签的交易记录
        # 使用 OR 条件匹配任意源标签
        from sqlalchemy import or_

        conditions = [Trade.user_id == user_id]
        # JSONB @> 任一源标签
        for name in source_names:
            conditions.append(Trade.tags.op("@>")([name]))

        trades_result = await self.db.execute(
            select(Trade).where(or_(*conditions[1:]))
        )
        trades = list(trades_result.scalars().all())

        updated_trades = 0
        for trade in trades:
            if not trade.tags:
                continue
            new_tags = []
            for t in trade.tags:
                if t in source_names:
                    if target_name not in new_tags:
                        new_tags.append(target_name)
                else:
                    if t not in new_tags:
                        new_tags.append(t)
            if new_tags != trade.tags:
                trade.tags = new_tags
                updated_trades += 1

        # 更新目标标签使用计数
        target_tag.usage_count += updated_trades

        # 删除源标签
        for tag in source_tags:
            await self.db.delete(tag)

        await self.db.flush()

        return {
            "merged_count": len(source_tags),
            "updated_trades": updated_trades,
            "deleted_tags": len(source_tags),
        }
