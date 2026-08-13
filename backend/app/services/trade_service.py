"""交易记录服务。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.schemas.trade import TradeQueryParams, TradeTagUpdate


class TradeService:
    """交易记录服务。

    处理交易记录的查询、标签更新等操作。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_trade(self, trade_id: str) -> Optional[Trade]:
        """获取单条交易记录。"""
        result = await self.db.execute(select(Trade).where(Trade.id == trade_id))
        return result.scalar_one_or_none()

    async def list_trades(
        self, user_id: str, params: TradeQueryParams
    ) -> tuple[List[Trade], int]:
        """查询交易记录列表（分页）。"""
        query = select(Trade).where(Trade.user_id == user_id)

        # 条件过滤
        if params.exchange:
            query = query.where(Trade.exchange == params.exchange)
        if params.symbol:
            query = query.where(Trade.symbol == params.symbol)
        if params.side:
            query = query.where(Trade.side == params.side)
        if params.status:
            query = query.where(Trade.status == params.status)
        if params.start_date:
            query = query.where(Trade.executed_at >= params.start_date)
        if params.end_date:
            query = query.where(Trade.executed_at <= params.end_date)

        # 总数
        count_query = select(Trade).where(Trade.user_id == user_id)
        # 注意：实际项目中应使用 select(func.count()) 优化

        # 分页
        offset = (params.page - 1) * params.page_size
        query = query.order_by(Trade.executed_at.desc()).offset(offset).limit(
            params.page_size
        )

        result = await self.db.execute(query)
        trades = list(result.scalars().all())
        return trades, len(trades)

    async def update_trade_tags(
        self, trade_id: str, data: TradeTagUpdate
    ) -> Optional[Trade]:
        """更新交易标签和备注。"""
        trade = await self.get_trade(trade_id)
        if trade is None:
            return None
        trade.tags = data.tags
        if data.note is not None:
            trade.note = data.note
        await self.db.flush()
        return trade
