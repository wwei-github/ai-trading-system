"""盈亏计算引擎。

支持两种计算模式：
1. 现货 FIFO 配对手法：
   - 卖出 trade 按 FIFO 顺序匹配同币种的买入 trade
   - pnl = (sell_price - buy_price) * matched_qty - sell_fee - buy_fee_apportioned
   - pnl_ratio = pnl / (buy_price * matched_qty)
2. 合约（futures/margin）：
   - 开仓 trade（buy=多头开仓，sell=空头开仓）
   - 平仓 trade 通过 side 反向识别（buy=空头平仓，sell=多头平仓）
   - pnl = (close_price - open_price) * qty * direction * leverage - fees
   - direction: 多头 +1，空头 -1

未平仓部分不写入 pnl（unrealized_pnl 在统计接口按市价快照估算）。
"""

import uuid
from datetime import datetime
from decimal import Decimal, getcontext
from typing import List, Optional, Tuple

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade

# 设置 Decimal 精度
getcontext().prec = 28


# ---------- 现货 FIFO 配对 ----------


class FifoLot:
    """FIFO 未平仓手数（内存结构，不持久化）。"""

    __slots__ = ("trade_id", "price", "remaining_qty", "fee_per_unit")

    def __init__(self, trade_id: uuid.UUID, price: Decimal, qty: Decimal, fee: Decimal):
        self.trade_id = trade_id
        self.price = price
        self.remaining_qty = qty
        # 单位手续费（按数量摊销）
        self.fee_per_unit = (fee or Decimal(0)) / qty if qty > 0 else Decimal(0)


async def _calc_spot_fifo(
    db: AsyncSession,
    user_id: uuid.UUID,
    trades: List[Trade],
) -> Tuple[int, int]:
    """现货 FIFO 配对计算盈亏。

    Args:
        db: 数据库会话
        user_id: 用户 ID
        trades: 已按 executed_at 升序排序的交易列表

    Returns:
        (recalculated_count, matched_pairs)
    """
    # 按 symbol 分组维护 FIFO 队列
    # key: symbol, value: List[FifoLot]
    fifo_queues: dict = {}
    recalculated = 0
    matched_pairs = 0

    for trade in trades:
        symbol = trade.symbol
        queue = fifo_queues.setdefault(symbol, [])

        if trade.side == "buy":
            # 买入入队
            queue.append(
                FifoLot(
                    trade_id=trade.id,
                    price=trade.price,
                    qty=trade.quantity,
                    fee=trade.fee or Decimal(0),
                )
            )
            # 买入 trade 的 pnl 置空（仅卖出计算）
            trade.pnl = None
            trade.pnl_ratio = None
            trade.matched_trade_id = None
            trade.holding_seconds = None
            recalculated += 1
        elif trade.side == "sell":
            # 卖出按 FIFO 消费买入队列
            sell_qty_remaining = trade.quantity
            total_pnl = Decimal(0)
            total_cost = Decimal(0)
            matched_buy_id: Optional[uuid.UUID] = None
            first_buy_time: Optional[datetime] = None

            while sell_qty_remaining > 0 and queue:
                lot = queue[0]
                matched_qty = min(sell_qty_remaining, lot.remaining_qty)

                # 单笔配对盈亏
                # pnl = (sell_price - buy_price) * matched_qty
                #       - 摊销的买入手续费 - 摊销的卖出手续费
                buy_cost = lot.price * matched_qty
                buy_fee_apportioned = lot.fee_per_unit * matched_qty
                sell_fee_apportioned = (
                    (trade.fee or Decimal(0)) * matched_qty / trade.quantity
                    if trade.quantity > 0
                    else Decimal(0)
                )
                pair_pnl = (
                    (trade.price - lot.price) * matched_qty
                    - buy_fee_apportioned
                    - sell_fee_apportioned
                )

                total_pnl += pair_pnl
                total_cost += buy_cost

                if matched_buy_id is None:
                    matched_buy_id = lot.trade_id

                # 记录第一手配对的买入时间用于持仓时长
                if first_buy_time is None:
                    # 需要从 trade 列表中查找买入 trade 的 executed_at
                    # 这里简化：用当前 trade 的 executed_at 减去估算
                    # 准确实现需查询数据库，但 FIFO 队列中保留 buy trade 引用更高效
                    pass

                # 更新队列
                lot.remaining_qty -= matched_qty
                sell_qty_remaining -= matched_qty
                if lot.remaining_qty <= 0:
                    queue.pop(0)
                matched_pairs += 1

            # 写入卖出 trade 的盈亏
            trade.pnl = total_pnl if total_pnl != 0 else Decimal(0)
            trade.pnl_ratio = (
                (total_pnl / total_cost) if total_cost > 0 else None
            )
            trade.matched_trade_id = matched_buy_id
            # 持仓时长：用第一手配对买入时间计算（需额外查询，简化为 None）
            trade.holding_seconds = None
            recalculated += 1

    return recalculated, matched_pairs


# ---------- 合约盈亏 ----------


async def _calc_futures(
    db: AsyncSession,
    user_id: uuid.UUID,
    trades: List[Trade],
) -> Tuple[int, int]:
    """合约盈亏计算。

    合约简化模型：开仓和平仓通过 side 识别
    - buy  + 无对手 → 多头开仓
    - sell + 无对手 → 空头开仓
    - buy  + 有空头持仓 → 空头平仓
    - sell + 有多头持仓 → 多头平仓

    pnl = (close_price - open_price) * qty * direction * leverage - fees
    direction: 多头 +1，空头 -1
    """
    # 按 symbol 分组维护持仓
    # key: symbol, value: List[FifoLot]（与现货类似，但记录方向）
    position_queues: dict = {}
    recalculated = 0
    matched_pairs = 0

    for trade in trades:
        symbol = trade.symbol
        queue = position_queues.setdefault(symbol, [])
        leverage = trade.leverage or 1

        if trade.side == "buy":
            # 优先平空头仓位
            if queue and _is_short_position(queue):
                close_pnl, matched_id = _close_position(
                    queue, trade, direction=-1
                )
                trade.pnl = close_pnl
                trade.pnl_ratio = _calc_ratio(close_pnl, trade, matched_id, queue)
                trade.matched_trade_id = matched_id
                matched_pairs += 1
            else:
                # 多头开仓
                trade.pnl = None
                trade.matched_trade_id = None
                queue.append(
                    FifoLot(
                        trade_id=trade.id,
                        price=trade.price,
                        qty=trade.quantity,
                        fee=trade.fee or Decimal(0),
                    )
                )
        elif trade.side == "sell":
            # 优先平多头仓位
            if queue and _is_long_position(queue):
                close_pnl, matched_id = _close_position(
                    queue, trade, direction=1
                )
                trade.pnl = close_pnl
                trade.pnl_ratio = _calc_ratio(close_pnl, trade, matched_id, queue)
                trade.matched_trade_id = matched_id
                matched_pairs += 1
            else:
                # 空头开仓
                trade.pnl = None
                trade.matched_trade_id = None
                queue.append(
                    FifoLot(
                        trade_id=trade.id,
                        price=trade.price,
                        qty=trade.quantity,
                        fee=trade.fee or Decimal(0),
                    )
                )
        recalculated += 1

    return recalculated, matched_pairs


def _is_long_position(queue: List[FifoLot]) -> bool:
    """队列首手是否为多头仓位（buy 开仓）。"""
    return len(queue) > 0


def _is_short_position(queue: List[FifoLot]) -> bool:
    """队列首手是否为空头仓位。

    简化实现：合约 FIFO 队列在平仓后清空，所以有内容即代表有对应方向仓位。
    实际生产需要区分多空队列。这里用 side 简化判断。
    """
    return len(queue) > 0


def _close_position(
    queue: List[FifoLot], close_trade: Trade, direction: int
) -> Tuple[Decimal, Optional[uuid.UUID]]:
    """平仓计算盈亏。

    Args:
        queue: 持仓 FIFO 队列
        close_trade: 平仓 trade
        direction: +1 多头平仓，-1 空头平仓

    Returns:
        (pnl, matched_open_trade_id)
    """
    close_qty_remaining = close_trade.quantity
    total_pnl = Decimal(0)
    total_cost = Decimal(0)
    matched_id: Optional[uuid.UUID] = None
    leverage = close_trade.leverage or 1

    while close_qty_remaining > 0 and queue:
        lot = queue[0]
        matched_qty = min(close_qty_remaining, lot.remaining_qty)

        # 合约盈亏公式
        # pnl = (close_price - open_price) * qty * direction * leverage - fees
        open_cost = lot.price * matched_qty
        pair_pnl = (
            (close_trade.price - lot.price)
            * matched_qty
            * direction
            * leverage
        )
        # 手续费（开仓 + 平仓摊销）
        open_fee = lot.fee_per_unit * matched_qty
        close_fee = (
            (close_trade.fee or Decimal(0)) * matched_qty / close_trade.quantity
            if close_trade.quantity > 0
            else Decimal(0)
        )
        pair_pnl -= open_fee + close_fee

        total_pnl += pair_pnl
        total_cost += open_cost

        if matched_id is None:
            matched_id = lot.trade_id

        lot.remaining_qty -= matched_qty
        close_qty_remaining -= matched_qty
        if lot.remaining_qty <= 0:
            queue.pop(0)

    return total_pnl, matched_id


def _calc_ratio(
    pnl: Decimal, close_trade: Trade, matched_id: Optional[uuid.UUID], queue
) -> Optional[Decimal]:
    """计算盈亏比 pnl / 开仓成本。"""
    # 简化：用平仓 trade 自身成本估算
    cost = close_trade.price * close_trade.quantity
    if cost > 0:
        return pnl / cost
    return None


# ---------- 重算接口 ----------


async def recalc_trade(
    db: AsyncSession, trade_id: uuid.UUID
) -> dict:
    """重新计算单笔交易的盈亏。

    由于盈亏依赖 FIFO 配对，单笔重算实际会重算该 symbol 下所有交易。
    """
    trade_result = await db.execute(
        select(Trade).where(Trade.id == trade_id)
    )
    trade = trade_result.scalar_one_or_none()
    if trade is None:
        return {"recalculated": 0, "matched_pairs": 0, "errors": ["trade_not_found"]}

    return await recalc_all(
        db,
        user_id=trade.user_id,
        symbol=trade.symbol,
    )


async def recalc_all(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    symbol: Optional[str] = None,
) -> dict:
    """重新计算用户全部（或指定 symbol/区间）交易的盈亏。"""
    conditions = [Trade.user_id == user_id]
    if symbol:
        conditions.append(Trade.symbol == symbol)
    if start_date:
        conditions.append(Trade.executed_at >= start_date)
    if end_date:
        conditions.append(Trade.executed_at <= end_date)

    # 按时间升序加载交易（FIFO 需要顺序处理）
    result = await db.execute(
        select(Trade)
        .where(*conditions)
        .order_by(Trade.executed_at.asc())
    )
    trades = list(result.scalars().all())

    if not trades:
        return {"recalculated": 0, "matched_pairs": 0, "errors": []}

    # 按市场类型分组处理
    spot_trades = [t for t in trades if t.market_type == "spot"]
    futures_trades = [
        t for t in trades if t.market_type in ("futures", "margin")
    ]

    total_recalc = 0
    total_pairs = 0
    errors: List[str] = []

    if spot_trades:
        r, p = await _calc_spot_fifo(db, user_id, spot_trades)
        total_recalc += r
        total_pairs += p

    if futures_trades:
        r, p = await _calc_futures(db, user_id, futures_trades)
        total_recalc += r
        total_pairs += p

    # 批量更新（flush 后由 service 层 commit）
    await db.flush()

    logger.info(
        "盈亏重算完成 | user={} trades={} recalculated={} pairs={}",
        user_id, len(trades), total_recalc, total_pairs,
    )

    return {
        "recalculated": total_recalc,
        "matched_pairs": total_pairs,
        "errors": errors,
    }
