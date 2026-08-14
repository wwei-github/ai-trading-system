"""交易记录服务。

功能：
- 交易 CRUD（手动创建固定 source=manual）
- 来源只读保护（exchange_sync 仅允许更新 tags/note）
- 未验证邮箱每日 ≤10 条限制
- 多维筛选（标签 @> / 全文搜索 / 盈亏状态）
- CSV/XLSX 导入预览 + 去重 + 确认
- CSV/XLSX 流式导出
- 盈亏重算（委托给 pnl 引擎）
- 汇总数据（供统计服务调用）
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator, List, Optional, Tuple

from loguru import logger
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException
from app.models.trade import Trade
from app.models.trade_tag import TradeTag
from app.models.user import User
from app.schemas.trade import (
    TradeCreate,
    TradeImportItem,
    TradeQueryParams,
    TradeTagUpdate,
    TradeUpdate,
)
from app.services.pnl import recalc_all, recalc_trade

# 未验证邮箱用户每日手动交易上限
UNVERIFIED_DAILY_LIMIT = 10
# 去重容差（价格/数量/时间）
DEDUP_PRICE_TOLERANCE = Decimal("0.00000001")
DEDUP_QTY_TOLERANCE = Decimal("0.00000001")
DEDUP_TIME_TOLERANCE_SECONDS = 2


class TradeService:
    """交易记录服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- CRUD ----------

    async def create_trade(
        self, user: User, data: TradeCreate
    ) -> Trade:
        """手动创建交易记录。

        - source 固定为 manual
        - 未验证邮箱用户每日 ≤10 条限制
        - 创建后触发该 symbol 的盈亏重算
        """
        # 未验证邮箱每日限制
        await self._check_unverified_daily_limit(user)

        trade = Trade(
            user_id=user.id,
            account_id=data.account_id,
            exchange=data.exchange,
            symbol=data.symbol,
            market_type=data.market_type,
            side=data.side,
            order_type=data.order_type,
            price=data.price,
            quantity=data.quantity,
            leverage=data.leverage,
            fee=data.fee,
            fee_currency=data.fee_currency,
            status=data.status,
            strategy_id=data.strategy_id,
            tags=data.tags,
            note=data.note,
            exchange_order_id=data.exchange_order_id,
            source="manual",  # 固定来源
            executed_at=data.executed_at,
        )
        self.db.add(trade)
        await self.db.flush()
        await self.db.refresh(trade)

        # 同步标签使用计数
        if data.tags:
            await self._incr_tag_usage(user.id, data.tags)

        # 触发盈亏重算（同 symbol）
        try:
            await recalc_trade(self.db, trade.id)
            await self.db.refresh(trade)
        except Exception as e:
            logger.warning("盈亏重算失败（不影响创建）| trade={} err={}", trade.id, e)

        return trade

    async def get_trade(
        self, trade_id: uuid.UUID, user_id: Optional[uuid.UUID] = None
    ) -> Optional[Trade]:
        """获取单条交易记录（user_id 校验归属）。"""
        conditions = [Trade.id == trade_id]
        if user_id:
            conditions.append(Trade.user_id == user_id)
        result = await self.db.execute(
            select(Trade).where(*conditions)
        )
        return result.scalar_one_or_none()

    async def update_trade(
        self, trade_id: uuid.UUID, user_id: uuid.UUID, data: TradeUpdate
    ) -> Optional[Trade]:
        """更新交易记录。

        来源只读保护：
        - exchange_sync：仅允许更新 tags / note / strategy_id
        - manual/import/paper/live：允许更新全部字段
        """
        trade = await self.get_trade(trade_id, user_id)
        if trade is None:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # 来源只读保护
        if trade.source == "exchange_sync":
            readonly_fields = set(update_data.keys()) - {
                "tags", "note", "strategy_id",
            }
            if readonly_fields:
                raise ForbiddenException(
                    "交易所同步的交易记录仅允许更新标签、备注和策略关联",
                    detail={"readonly_fields": list(readonly_fields)},
                )

        # 应用更新
        for key, value in update_data.items():
            setattr(trade, key, value)

        await self.db.flush()
        await self.db.refresh(trade)

        # 价格/数量/方向变化时触发盈亏重算
        pnl_trigger_fields = {"price", "quantity", "side", "fee", "leverage", "executed_at"}
        if update_data.keys() & pnl_trigger_fields:
            try:
                await recalc_trade(self.db, trade.id)
                await self.db.refresh(trade)
            except Exception as e:
                logger.warning("盈亏重算失败（不影响更新）| trade={} err={}", trade.id, e)

        return trade

    async def delete_trade(
        self, trade_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """删除交易记录。

        - exchange_sync 来源禁止删除（需先停用同步）
        """
        trade = await self.get_trade(trade_id, user_id)
        if trade is None:
            return False

        if trade.source == "exchange_sync":
            raise ForbiddenException(
                "交易所同步的交易记录不可删除，请先停用账号同步或删除关联账号",
            )

        await self.db.delete(trade)
        await self.db.flush()
        return True

    # ---------- 多维筛选查询 ----------

    async def list_trades(
        self, user_id: uuid.UUID, params: TradeQueryParams
    ) -> Tuple[List[Trade], int]:
        """查询交易记录列表（分页 + 多条件筛选）。

        支持的筛选维度：
        - 时间范围 / 交易对 / 账号 / 策略 / 标签 / 方向 / 盈亏状态 / 交易所
        - 标签数组用 Postgres JSONB @> 操作符
        - 全文搜索（symbol ILIKE / note ILIKE）
        """
        conditions = [Trade.user_id == user_id]

        if params.exchange:
            conditions.append(Trade.exchange == params.exchange)
        if params.symbol:
            conditions.append(Trade.symbol == params.symbol)
        if params.account_id:
            conditions.append(Trade.account_id == params.account_id)
        if params.strategy_id:
            conditions.append(Trade.strategy_id == params.strategy_id)
        if params.side:
            conditions.append(Trade.side == params.side)
        if params.status:
            conditions.append(Trade.status == params.status)
        if params.source:
            conditions.append(Trade.source == params.source)
        if params.start_date:
            conditions.append(Trade.executed_at >= params.start_date)
        if params.end_date:
            conditions.append(Trade.executed_at <= params.end_date)

        # 标签数组筛选（JSONB @> 操作符）
        if params.tags:
            conditions.append(Trade.tags.op("@>")(params.tags))

        # 全文搜索（symbol / note）
        if params.search:
            search_pattern = f"%{params.search}%"
            conditions.append(
                or_(
                    Trade.symbol.ilike(search_pattern),
                    Trade.note.ilike(search_pattern),
                )
            )

        # 盈亏状态筛选
        if params.pnl_status:
            if params.pnl_status == "profit":
                conditions.append(Trade.pnl > 0)
            elif params.pnl_status == "loss":
                conditions.append(Trade.pnl < 0)
            elif params.pnl_status == "breakeven":
                conditions.append(Trade.pnl == 0)
            elif params.pnl_status == "unrealized":
                conditions.append(Trade.pnl.is_(None))

        # 总数查询
        count_query = select(func.count(Trade.id)).where(*conditions)
        total = (await self.db.execute(count_query)).scalar_one()

        # 排序字段白名单
        sort_field_map = {
            "executed_at": Trade.executed_at,
            "price": Trade.price,
            "quantity": Trade.quantity,
            "pnl": Trade.pnl,
            "fee": Trade.fee,
            "created_at": Trade.created_at,
        }
        sort_col = sort_field_map.get(params.sort_by, Trade.executed_at)
        order = sort_col.asc() if params.sort_order == "asc" else sort_col.desc()

        # 分页查询
        offset = (params.page - 1) * params.page_size
        query = (
            select(Trade)
            .where(*conditions)
            .order_by(order)
            .offset(offset)
            .limit(params.page_size)
        )
        result = await self.db.execute(query)
        trades = list(result.scalars().all())
        return trades, total

    async def update_trade_tags(
        self, trade_id: uuid.UUID, user_id: uuid.UUID, data: TradeTagUpdate
    ) -> Optional[Trade]:
        """更新交易标签和备注（exchange_sync 来源也允许）。"""
        trade = await self.get_trade(trade_id, user_id)
        if trade is None:
            return None
        if data.tags is not None:
            trade.tags = data.tags
            await self._incr_tag_usage(user_id, data.tags)
        if data.note is not None:
            trade.note = data.note
        await self.db.flush()
        await self.db.refresh(trade)
        return trade

    # ---------- 盈亏重算 ----------

    async def recalc_pnl(
        self,
        user_id: uuid.UUID,
        trade_ids: Optional[List[uuid.UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
    ) -> dict:
        """盈亏重算（委托给 pnl 引擎）。"""
        if trade_ids:
            # 单笔或多笔重算
            errors: List[str] = []
            total_recalc = 0
            total_pairs = 0
            for tid in trade_ids:
                result = await recalc_trade(self.db, tid)
                total_recalc += result["recalculated"]
                total_pairs += result["matched_pairs"]
                errors.extend(result.get("errors", []))
            return {
                "recalculated": total_recalc,
                "matched_pairs": total_pairs,
                "errors": errors,
            }
        return await recalc_all(
            self.db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            symbol=symbol,
        )

    # ---------- 导入预览 + 去重 ----------

    async def preview_import(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        trades: List[TradeImportItem],
    ) -> dict:
        """导入预览：校验 + 去重检测。

        去重键 = 交易对 + 价格 + 数量 + 时间 ± 极小容差
        """
        rows: List[dict] = []
        valid_count = 0
        invalid_count = 0
        duplicates = 0

        # 查询已存在的同账号交易用于去重
        existing_trades_result = await self.db.execute(
            select(Trade).where(Trade.account_id == account_id)
        )
        existing_trades = list(existing_trades_result.scalars().all())

        for idx, item in enumerate(trades):
            row = {
                "row_index": idx,
                "valid": True,
                "data": item,
                "error": None,
                "duplicate": False,
            }
            try:
                # 基础校验（Pydantic 已在 schema 层完成，这里补充业务校验）
                if item.side not in ("buy", "sell"):
                    raise ValueError(f"无效的方向: {item.side}")
                if item.market_type not in ("spot", "futures", "margin"):
                    raise ValueError(f"无效的市场类型: {item.market_type}")

                # 去重检测
                is_dup = self._is_duplicate(item, existing_trades)
                if is_dup:
                    row["duplicate"] = True
                    duplicates += 1
                    # 重复行仍标记为 valid，但 import 时跳过
                else:
                    valid_count += 1
            except Exception as e:
                row["valid"] = False
                row["error"] = str(e)
                invalid_count += 1

            rows.append(row)

        return {
            "total": len(trades),
            "valid": valid_count,
            "invalid": invalid_count,
            "duplicates": duplicates,
            "rows": rows,
        }

    def _is_duplicate(
        self, item: TradeImportItem, existing: List[Trade]
    ) -> bool:
        """去重检测：交易对 + 价格 + 数量 + 时间 ± 容差。"""
        for t in existing:
            if t.symbol != item.symbol:
                continue
            if abs(t.price - item.price) > DEDUP_PRICE_TOLERANCE:
                continue
            if abs(t.quantity - item.quantity) > DEDUP_QTY_TOLERANCE:
                continue
            time_diff = abs(
                (t.executed_at - item.executed_at).total_seconds()
            )
            if time_diff > DEDUP_TIME_TOLERANCE_SECONDS:
                continue
            return True
        return False

    async def confirm_import(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        trades: List[TradeImportItem],
        skip_duplicates: bool = True,
    ) -> dict:
        """确认导入（实际写入数据库）。

        Args:
            skip_duplicates: True 时跳过重复行；False 时仍写入（允许重复）
        """
        # 再次预览以获取重复信息
        preview = await self.preview_import(user_id, account_id, trades)

        total = len(trades)
        imported = 0
        skipped = 0
        errors: List[str] = []

        for idx, row in enumerate(preview["rows"]):
            if not row["valid"]:
                skipped += 1
                errors.append(f"第 {idx + 1} 行校验失败: {row['error']}")
                continue
            if row["duplicate"] and skip_duplicates:
                skipped += 1
                continue

            item = trades[idx]
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
                    source="import",  # 导入来源标记
                    executed_at=item.executed_at,
                )
                self.db.add(trade)
                await self.db.flush()
                imported += 1

                # 标签使用计数
                if item.tags:
                    await self._incr_tag_usage(user_id, item.tags)
            except Exception as e:
                skipped += 1
                errors.append(f"第 {idx + 1} 行导入失败: {str(e)}")

        # 触发盈亏重算
        if imported > 0:
            try:
                await recalc_all(self.db, user_id=user_id)
            except Exception as e:
                logger.warning("导入后盈亏重算失败 | err={}", e)

        return {
            "total": total,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        }

    # ---------- 流式导出 ----------

    async def export_trades_csv(
        self, user_id: uuid.UUID, params: TradeQueryParams
    ) -> AsyncIterator[str]:
        """流式导出 CSV。"""
        # 导出时放大分页
        export_params = params.model_copy(
            update={"page": 1, "page_size": 100}
        )
        trades, _ = await self.list_trades(user_id, export_params)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(self._export_headers())
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for t in trades:
            writer.writerow(self._trade_to_row(t))
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    async def export_trades_json(
        self, user_id: uuid.UUID, params: TradeQueryParams
    ) -> str:
        """导出 JSON 格式。"""
        import json

        export_params = params.model_copy(
            update={"page": 1, "page_size": 100}
        )
        trades, _ = await self.list_trades(user_id, export_params)

        data = []
        for t in trades:
            data.append(self._trade_to_dict(t))
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)

    def _export_headers(self) -> List[str]:
        return [
            "id", "exchange", "symbol", "market_type", "side", "order_type",
            "price", "quantity", "leverage", "fee", "fee_currency", "status",
            "source", "tags", "note", "exchange_order_id",
            "pnl", "pnl_ratio", "matched_trade_id", "holding_seconds",
            "executed_at", "created_at",
        ]

    def _trade_to_row(self, t: Trade) -> List[Any]:
        return [
            str(t.id), t.exchange, t.symbol, t.market_type, t.side, t.order_type,
            str(t.price), str(t.quantity), t.leverage or "",
            str(t.fee) if t.fee else "", t.fee_currency or "", t.status,
            t.source, ",".join(t.tags) if t.tags else "", t.note or "",
            t.exchange_order_id or "",
            str(t.pnl) if t.pnl is not None else "",
            str(t.pnl_ratio) if t.pnl_ratio is not None else "",
            str(t.matched_trade_id) if t.matched_trade_id else "",
            t.holding_seconds or "",
            t.executed_at.isoformat() if t.executed_at else "",
            t.created_at.isoformat() if t.created_at else "",
        ]

    def _trade_to_dict(self, t: Trade) -> dict:
        return {
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
            "source": t.source,
            "tags": t.tags,
            "note": t.note,
            "exchange_order_id": t.exchange_order_id,
            "pnl": str(t.pnl) if t.pnl is not None else None,
            "pnl_ratio": str(t.pnl_ratio) if t.pnl_ratio is not None else None,
            "matched_trade_id": str(t.matched_trade_id) if t.matched_trade_id else None,
            "holding_seconds": t.holding_seconds,
            "executed_at": t.executed_at.isoformat() if t.executed_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }

    # ---------- 汇总数据 ----------

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
                func.sum(Trade.pnl).label("total_pnl"),
                func.count(Trade.id).filter(Trade.pnl > 0).label("profit_count"),
                func.count(Trade.id).filter(Trade.pnl < 0).label("loss_count"),
            ).where(Trade.user_id == user_id)
        )
        row = result.one()
        return {
            "total_trades": row.total_trades or 0,
            "total_volume": row.total_volume or 0,
            "total_fee": row.total_fee or 0,
            "buy_count": row.buy_count or 0,
            "sell_count": row.sell_count or 0,
            "total_pnl": row.total_pnl or 0,
            "profit_count": row.profit_count or 0,
            "loss_count": row.loss_count or 0,
        }

    # ---------- 内部辅助 ----------

    async def _check_unverified_daily_limit(self, user: User) -> None:
        """未验证邮箱用户每日手动交易 ≤10 条。"""
        if user.email_verified:
            return

        # 查询今日已创建的手动交易数
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        count_result = await self.db.execute(
            select(func.count(Trade.id)).where(
                Trade.user_id == user.id,
                Trade.source == "manual",
                Trade.created_at >= today_start,
            )
        )
        today_count = count_result.scalar_one()
        if today_count >= UNVERIFIED_DAILY_LIMIT:
            raise ForbiddenException(
                f"未验证邮箱用户每日最多创建 {UNVERIFIED_DAILY_LIMIT} 条手动交易，"
                "请验证邮箱后继续",
                detail={
                    "today_count": today_count,
                    "limit": UNVERIFIED_DAILY_LIMIT,
                },
            )

    async def _incr_tag_usage(
        self, user_id: uuid.UUID, tag_names: List[str]
    ) -> None:
        """递增标签使用计数（不存在则创建）。"""
        for name in tag_names:
            result = await self.db.execute(
                select(TradeTag).where(
                    TradeTag.user_id == user_id,
                    TradeTag.name == name,
                )
            )
            tag = result.scalar_one_or_none()
            if tag is None:
                tag = TradeTag(user_id=user_id, name=name, usage_count=1)
                self.db.add(tag)
            else:
                tag.usage_count += 1
        await self.db.flush()
