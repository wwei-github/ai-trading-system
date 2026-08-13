"""交易记录服务。"""

import csv
import io
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.schemas.trade import (
    TradeImportItem,
    TradeQueryParams,
    TradeTagUpdate,
)


class TradeService:
    """交易记录服务。

    处理交易记录的查询、标签更新、批量导入、导出等操作。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_trade(
        self, trade_id: uuid.UUID
    ) -> Optional[Trade]:
        """获取单条交易记录。"""
        result = await self.db.execute(
            select(Trade).where(Trade.id == trade_id)
        )
        return result.scalar_one_or_none()

    async def list_trades(
        self, user_id: uuid.UUID, params: TradeQueryParams
    ) -> Tuple[List[Trade], int]:
        """查询交易记录列表（分页 + 多条件筛选）。

        Returns:
            (trades, total) 元组
        """
        # 构建查询条件
        conditions = [Trade.user_id == user_id]
        if params.exchange:
            conditions.append(Trade.exchange == params.exchange)
        if params.symbol:
            conditions.append(Trade.symbol == params.symbol)
        if params.side:
            conditions.append(Trade.side == params.side)
        if params.status:
            conditions.append(Trade.status == params.status)
        if params.strategy_id:
            conditions.append(Trade.strategy_id == params.strategy_id)
        if params.start_date:
            conditions.append(Trade.executed_at >= params.start_date)
        if params.end_date:
            conditions.append(Trade.executed_at <= params.end_date)

        # 总数查询
        count_query = select(func.count(Trade.id)).where(*conditions)
        total = (await self.db.execute(count_query)).scalar_one()

        # 分页查询
        offset = (params.page - 1) * params.page_size
        query = (
            select(Trade)
            .where(*conditions)
            .order_by(Trade.executed_at.desc())
            .offset(offset)
            .limit(params.page_size)
        )
        result = await self.db.execute(query)
        trades = list(result.scalars().all())
        return trades, total

    async def update_trade_tags(
        self, trade_id: uuid.UUID, data: TradeTagUpdate
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

    async def import_trades(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        trades: List[TradeImportItem],
    ) -> dict:
        """批量导入交易记录。

        Returns:
            {"total": int, "imported": int, "skipped": int, "errors": [...]}
        """
        total = len(trades)
        imported = 0
        skipped = 0
        errors = []

        for idx, item in enumerate(trades):
            try:
                trade = Trade(
                    user_id=user_id,
                    account_id=account_id,
                    exchange=item.exchange,
                    symbol=item.symbol,
                    market_type=item.market_type,
                    side=item.side,
                    order_type=item.order_type,
                    price=item.price,
                    quantity=item.quantity,
                    leverage=item.leverage,
                    fee=item.fee,
                    fee_currency=item.fee_currency,
                    status=item.status,
                    strategy_id=item.strategy_id,
                    tags=item.tags,
                    note=item.note,
                    exchange_order_id=item.exchange_order_id,
                    executed_at=item.executed_at,
                )
                self.db.add(trade)
                await self.db.flush()
                imported += 1
            except Exception as e:
                skipped += 1
                errors.append(f"第 {idx + 1} 条导入失败: {str(e)}")

        return {
            "total": total,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        }

    async def export_trades(
        self,
        user_id: uuid.UUID,
        params: TradeQueryParams,
        fmt: str = "csv",
    ) -> str:
        """导出交易记录为 CSV 或 JSON 字符串。

        Args:
            user_id: 用户 ID
            params: 查询参数（page_size 放大到最大值 100 以导出更多数据）
            fmt: 导出格式 csv / json

        Returns:
            导出的字符串内容
        """
        # 导出时使用最大分页
        export_params = params.model_copy(
            update={"page": 1, "page_size": 100}
        )
        trades, _ = await self.list_trades(user_id, export_params)

        if fmt == "json":
            import json

            data = []
            for t in trades:
                data.append(
                    {
                        "id": str(t.id),
                        "exchange": t.exchange,
                        "symbol": t.symbol,
                        "market_type": t.market_type,
                        "side": t.side,
                        "order_type": t.order_type,
                        "price": str(t.price),
                        "quantity": str(t.quantity),
                        "leverage": t.leverage,
                        "fee": str(t.fee) if t.fee else None,
                        "fee_currency": t.fee_currency,
                        "status": t.status,
                        "tags": t.tags,
                        "note": t.note,
                        "exchange_order_id": t.exchange_order_id,
                        "executed_at": t.executed_at.isoformat()
                        if t.executed_at
                        else None,
                    }
                )
            return json.dumps(data, ensure_ascii=False, indent=2)

        # 默认 CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "exchange",
                "symbol",
                "market_type",
                "side",
                "order_type",
                "price",
                "quantity",
                "leverage",
                "fee",
                "fee_currency",
                "status",
                "tags",
                "note",
                "exchange_order_id",
                "executed_at",
            ]
        )
        for t in trades:
            writer.writerow(
                [
                    str(t.id),
                    t.exchange,
                    t.symbol,
                    t.market_type,
                    t.side,
                    t.order_type,
                    str(t.price),
                    str(t.quantity),
                    t.leverage or "",
                    str(t.fee) if t.fee else "",
                    t.fee_currency or "",
                    t.status,
                    ",".join(t.tags) if t.tags else "",
                    t.note or "",
                    t.exchange_order_id or "",
                    t.executed_at.isoformat() if t.executed_at else "",
                ]
            )
        return output.getvalue()

    async def get_trade_summary_raw(
        self, user_id: uuid.UUID
    ) -> dict:
        """获取交易汇总原始数据（供统计服务调用）。"""
        result = await self.db.execute(
            select(
                func.count(Trade.id).label("total_trades"),
                func.sum(Trade.price * Trade.quantity).label("total_volume"),
                func.sum(Trade.fee).label("total_fee"),
                func.sum(
                    func.case((Trade.side == "buy", 1), else_=0)
                ).label("buy_count"),
                func.sum(
                    func.case((Trade.side == "sell", 1), else_=0)
                ).label("sell_count"),
            ).where(Trade.user_id == user_id)
        )
        row = result.one()
        return {
            "total_trades": row.total_trades or 0,
            "total_volume": row.total_volume or 0,
            "total_fee": row.total_fee or 0,
            "buy_count": row.buy_count or 0,
            "sell_count": row.sell_count or 0,
        }
