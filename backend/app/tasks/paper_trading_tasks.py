"""模拟交易引擎任务（Stage 6.6，对齐 PRD §5.6.4）。

由 Celery Beat 定时调度（每分钟），负责：
1. 拉取所有 running 状态的 PaperAccount
2. 获取最新 K 线（CCXT 公开接口 / DB klines 表）
3. 调用回测引擎的信号生成函数判断当前信号
4. 信号变化时执行虚拟成交，更新账号权益/持仓
5. 通过 Redis 发布实时更新（供前端 WS/SSE 订阅）

实盘信号生成（Stage 6.7）也复用本模块的信号检测逻辑，
生成 LiveOrder（pending）等待用户确认。
"""

import asyncio
import datetime
import json
import uuid
from datetime import timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import select

from app.tasks import celery_app
from app.core.database import redis_client


# ---------- 实时更新发布 ----------

PAPER_CHANNEL_PREFIX = "paper_trading:update"
LIVE_CHANNEL_PREFIX = "live_trading:signal"


async def _publish_paper_update(paper_account_id: str, payload: Dict[str, Any]):
    """通过 Redis 发布模拟交易更新（供前端 WS/SSE 订阅）。"""
    try:
        if redis_client is None:
            return
        channel = f"{PAPER_CHANNEL_PREFIX}:{paper_account_id}"
        payload["timestamp"] = datetime.datetime.now(timezone.utc).isoformat()
        await redis_client.publish(channel, json.dumps(payload, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning("发布模拟交易更新失败 | {} {}", paper_account_id, e)


async def _publish_live_signal(instance_id: str, order_payload: Dict[str, Any]):
    """通过 Redis 发布实盘信号（供前端 WS/SSE 订阅）。"""
    try:
        if redis_client is None:
            return
        channel = f"{LIVE_CHANNEL_PREFIX}:{instance_id}"
        payload = {
            **order_payload,
            "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
        }
        await redis_client.publish(channel, json.dumps(payload, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning("发布实盘信号失败 | {} {}", instance_id, e)


# ---------- K 线拉取（复用 backtest_tasks 逻辑） ----------

async def _fetch_recent_klines(
    symbol: str, timeframe: str, limit: int = 200, exchange: str = "binance"
) -> pd.DataFrame:
    """拉取最近 N 根 K 线。"""
    from app.exchange.ccxt_client import CCXTClient

    client = CCXTClient(exchange=exchange, api_key="", api_secret="")
    try:
        await client.load_markets()
        ohlcv = await client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not ohlcv:
            return pd.DataFrame()
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df
    finally:
        await client.close()


# ---------- 信号生成（复用回测引擎） ----------

def _detect_strategy_type(strategy, params: Dict[str, Any]) -> str:
    """从策略推断信号类型（复用 backtest_tasks 逻辑）。"""
    from app.tasks.backtest_tasks import _detect_strategy_type as _detect
    return _detect(strategy, params)


def _generate_current_signal(
    df: pd.DataFrame, strategy_type: str, params: Dict[str, Any]
) -> int:
    """生成当前最新一根 K 线的持仓信号（1=持仓，0=空仓）。"""
    from app.utils.backtest_engine import _generate_signals

    if df.empty:
        return 0
    signal_series = _generate_signals(df, strategy_type, params)
    if len(signal_series) == 0:
        return 0
    return int(signal_series.iloc[-1])


# ---------- 模拟交易执行 ----------

async def _execute_paper_trade(
    session,
    account,
    side: str,
    price: float,
    quantity: float,
    signal_source: str,
    fee_rate: float = 0.001,
) -> Dict[str, Any]:
    """执行一笔虚拟成交，更新账号状态。"""
    from app.models.paper_trading import PaperTrade

    fee = price * quantity * fee_rate

    # 计算平仓盈亏（卖出时）
    realized_pnl = None
    if side == "sell" and account.position > 0 and account.avg_entry_price:
        # FIFO 简化：全部平仓
        cost = account.avg_entry_price * min(quantity, account.position)
        revenue = price * min(quantity, account.position)
        realized_pnl = revenue - cost - fee

    # 更新账号持仓与资金
    if side == "buy":
        cost = price * quantity + fee
        if cost > float(account.available_cash):
            return {"executed": False, "reason": "资金不足"}
        # 更新持仓均价
        old_position = account.position
        new_position = old_position + quantity
        if new_position > 0:
            account.avg_entry_price = (
                (account.avg_entry_price or 0) * old_position + price * quantity
            ) / new_position
        account.position = new_position
        account.available_cash = Decimal(str(float(account.available_cash) - cost))
    elif side == "sell":
        sell_qty = min(quantity, account.position)
        proceeds = price * sell_qty - fee
        account.position = max(0, account.position - sell_qty)
        if account.position == 0:
            account.avg_entry_price = None
        account.available_cash = Decimal(str(float(account.available_cash) + proceeds))
        if realized_pnl is not None:
            account.total_pnl = Decimal(str(float(account.total_pnl) + realized_pnl))
        quantity = sell_qty  # 实际成交量

    # 更新当前权益 = 可用资金 + 持仓市值
    current_equity = float(account.available_cash) + account.position * price
    account.current_equity = Decimal(str(round(current_equity, 2)))
    account.total_trades += 1

    # 写入交易记录
    trade = PaperTrade(
        paper_account_id=account.id,
        strategy_id=account.strategy_id,
        user_id=account.user_id,
        symbol=account.symbol,
        side=side,
        order_type="market",
        price=price,
        quantity=quantity,
        fee=fee,
        executed_at=datetime.datetime.now(timezone.utc),
        signal_source=signal_source,
        realized_pnl=realized_pnl,
    )
    session.add(trade)
    await session.flush()

    return {
        "executed": True,
        "trade_id": str(trade.id),
        "side": side,
        "price": price,
        "quantity": quantity,
        "fee": fee,
        "realized_pnl": realized_pnl,
        "current_equity": float(account.current_equity),
        "position": account.position,
        "available_cash": float(account.available_cash),
    }


# ---------- 模拟交易主循环 ----------

async def _run_paper_trading_tick_async() -> Dict[str, Any]:
    """模拟交易定时调度：处理所有 running 状态的虚拟账号。"""
    from app.core.database import async_session_maker
    from app.models.paper_trading import PaperAccount
    from app.models.strategy import Strategy

    processed = 0
    traded = 0
    errors = 0

    async with async_session_maker() as session:
        # 拉取所有 running 状态的模拟账号
        result = await session.execute(
            select(PaperAccount).where(PaperAccount.status == "running")
        )
        accounts = list(result.scalars().all())

        if not accounts:
            return {"processed": 0, "traded": 0, "errors": 0}

        logger.info("模拟交易 tick：处理 {} 个运行中账号", len(accounts))

        for account in accounts:
            try:
                processed += 1

                # 加载策略
                strat_result = await session.execute(
                    select(Strategy).where(Strategy.id == account.strategy_id)
                )
                strategy = strat_result.scalar_one_or_none()
                if strategy is None:
                    logger.warning("策略不存在，跳过 | paper_account={}", account.id)
                    continue

                # 合并参数
                params: Dict[str, Any] = {}
                if strategy.params:
                    params.update(strategy.params)
                if account.strategy_params:
                    params.update(account.strategy_params)

                # 拉取最近 K 线
                df = await _fetch_recent_klines(
                    symbol=account.symbol,
                    timeframe=account.timeframe,
                    limit=200,
                )
                if df.empty or len(df) < 30:
                    logger.warning(
                        "K 线数据不足，跳过 | paper_account={} bars={}",
                        account.id, len(df),
                    )
                    continue

                # 生成当前信号
                strategy_type = _detect_strategy_type(strategy, params)
                current_signal = _generate_current_signal(df, strategy_type, params)

                # 获取最新价格
                latest_price = float(df["close"].iloc[-1])

                # 判断信号变化
                # current_signal: 1=应持仓, 0=应空仓
                # account.position > 0: 已持仓
                should_hold = current_signal == 1
                is_holding = account.position > 0

                if should_hold and not is_holding:
                    # 开仓信号：买入
                    # 简化：使用 95% 可用资金买入
                    buy_amount = float(account.available_cash) * 0.95 / latest_price
                    if buy_amount > 0:
                        result = await _execute_paper_trade(
                            session, account, "buy", latest_price, buy_amount,
                            signal_source=f"{strategy_type}_buy_signal",
                        )
                        if result.get("executed"):
                            traded += 1
                            await _publish_paper_update(str(account.id), {
                                "type": "trade",
                                "side": "buy",
                                "price": latest_price,
                                "quantity": buy_amount,
                                "current_equity": result["current_equity"],
                                "position": result["position"],
                            })

                elif not should_hold and is_holding:
                    # 平仓信号：卖出全部
                    sell_qty = account.position
                    if sell_qty > 0:
                        result = await _execute_paper_trade(
                            session, account, "sell", latest_price, sell_qty,
                            signal_source=f"{strategy_type}_sell_signal",
                        )
                        if result.get("executed"):
                            traded += 1
                            await _publish_paper_update(str(account.id), {
                                "type": "trade",
                                "side": "sell",
                                "price": latest_price,
                                "quantity": sell_qty,
                                "realized_pnl": result.get("realized_pnl"),
                                "current_equity": result["current_equity"],
                                "position": result["position"],
                            })

                # 推送权益快照（无论是否交易）
                await _publish_paper_update(str(account.id), {
                    "type": "tick",
                    "price": latest_price,
                    "current_equity": float(account.current_equity),
                    "position": account.position,
                    "available_cash": float(account.available_cash),
                    "unrealized_pnl": (
                        (latest_price - (account.avg_entry_price or 0)) * account.position
                        if account.position > 0 and account.avg_entry_price else 0
                    ),
                })

            except Exception as e:
                errors += 1
                logger.exception("模拟交易 tick 异常 | paper_account={}", account.id)

        await session.commit()

    logger.info("模拟交易 tick 完成 | processed={} traded={} errors={}", processed, traded, errors)
    return {"processed": processed, "traded": traded, "errors": errors}


# ---------- 实盘信号生成 ----------

async def _run_live_signal_tick_async() -> Dict[str, Any]:
    """实盘信号定时调度：处理所有 running 状态的实盘实例。

    信号生成后创建 LiveOrder（pending），半自动模式等待用户确认。
    """
    from app.core.database import async_session_maker
    from app.models.live_trading import LiveOrder, LiveStrategyInstance
    from app.models.strategy import Strategy

    processed = 0
    signals = 0
    errors = 0

    async with async_session_maker() as session:
        result = await session.execute(
            select(LiveStrategyInstance).where(
                LiveStrategyInstance.status == "running"
            )
        )
        instances = list(result.scalars().all())

        if not instances:
            return {"processed": 0, "signals": 0, "errors": 0}

        logger.info("实盘信号 tick：处理 {} 个运行中实例", len(instances))

        for instance in instances:
            try:
                processed += 1

                # 加载策略
                strat_result = await session.execute(
                    select(Strategy).where(Strategy.id == instance.strategy_id)
                )
                strategy = strat_result.scalar_one_or_none()
                if strategy is None:
                    continue

                # 合并参数
                params: Dict[str, Any] = {}
                if strategy.params:
                    params.update(strategy.params)
                if instance.strategy_params:
                    params.update(instance.strategy_params)

                # 拉取最近 K 线
                df = await _fetch_recent_klines(
                    symbol=instance.symbol,
                    timeframe=instance.timeframe,
                    limit=200,
                )
                if df.empty or len(df) < 30:
                    continue

                # 生成当前信号
                strategy_type = _detect_strategy_type(strategy, params)
                current_signal = _generate_current_signal(df, strategy_type, params)
                latest_price = float(df["close"].iloc[-1])

                # 检查最近是否已有 pending 订单（避免重复生成）
                recent_pending = await session.execute(
                    select(LiveOrder).where(
                        LiveOrder.instance_id == instance.id,
                        LiveOrder.status == "pending",
                    ).limit(1)
                )
                if recent_pending.scalar_one_or_none() is not None:
                    continue  # 已有待确认订单

                # 信号逻辑：简化版，current_signal=1 生成买入信号
                # 实际生产中应基于持仓状态判断开/平仓
                if current_signal == 1:
                    # 生成买入信号订单
                    # 简化：使用固定金额 1000 USDT
                    suggested_amount = 1000.0 / latest_price
                    order = LiveOrder(
                        instance_id=instance.id,
                        strategy_id=instance.strategy_id,
                        user_id=instance.user_id,
                        account_id=instance.account_id,
                        symbol=instance.symbol,
                        side="buy",
                        order_type="market",
                        suggested_price=latest_price,
                        suggested_amount=suggested_amount,
                        signal_strength=3,
                        reason=f"{strategy_type} 买入信号",
                        status="pending",
                        signal_at=datetime.datetime.now(timezone.utc),
                        expires_at=datetime.datetime.now(timezone.utc) + datetime.timedelta(seconds=60),
                    )
                    session.add(order)
                    instance.total_signals += 1
                    await session.flush()

                    signals += 1
                    await _publish_live_signal(str(instance.id), {
                        "type": "signal",
                        "order_id": str(order.id),
                        "side": "buy",
                        "symbol": instance.symbol,
                        "suggested_price": latest_price,
                        "suggested_amount": suggested_amount,
                        "reason": order.reason,
                        "expires_at": order.expires_at.isoformat() if order.expires_at else None,
                    })

            except Exception as e:
                errors += 1
                logger.exception("实盘信号 tick 异常 | instance={}", instance.id)

        await session.commit()

    logger.info("实盘信号 tick 完成 | processed={} signals={} errors={}", processed, signals, errors)
    return {"processed": processed, "signals": signals, "errors": errors}


# ---------- Celery 任务入口 ----------

@celery_app.task(name="paper_trading_tick")
def paper_trading_tick() -> dict:
    """模拟交易定时调度（每分钟由 Celery Beat 触发）。"""
    return asyncio.run(_run_paper_trading_tick_async())


@celery_app.task(name="live_signal_tick")
def live_signal_tick() -> dict:
    """实盘信号定时调度（每分钟由 Celery Beat 触发）。"""
    return asyncio.run(_run_live_signal_tick_async())
