"""策略服务。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy import Strategy
from app.schemas.strategy import StrategyCreate, StrategyUpdate


class StrategyService:
    """策略服务。

    处理策略的增删改查和回测管理。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_strategy(
        self, user_id: str, data: StrategyCreate
    ) -> Strategy:
        """创建策略。"""
        strategy = Strategy(
            user_id=user_id,
            name=data.name,
            category=data.category,
            description=data.description,
            rules=data.rules,
            params=data.params,
            source_book_id=data.source_book_id,
        )
        self.db.add(strategy)
        await self.db.flush()
        return strategy

    async def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """获取策略详情。"""
        result = await self.db.execute(
            select(Strategy).where(Strategy.id == strategy_id)
        )
        return result.scalar_one_or_none()

    async def list_strategies(self, user_id: str) -> List[Strategy]:
        """获取用户的全部策略。"""
        result = await self.db.execute(
            select(Strategy).where(Strategy.user_id == user_id)
        )
        return list(result.scalars().all())

    async def update_strategy(
        self, strategy_id: str, data: StrategyUpdate
    ) -> Optional[Strategy]:
        """更新策略。"""
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(strategy, key, value)
        await self.db.flush()
        return strategy

    async def delete_strategy(self, strategy_id: str) -> bool:
        """删除策略。"""
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            return False
        await self.db.delete(strategy)
        await self.db.flush()
        return True
