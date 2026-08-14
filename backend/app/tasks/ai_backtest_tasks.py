"""AI 回测 Celery 异步任务。"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.database import redis_client
from app.models.ai_backtest import AIBacktest
from app.models.ai_backtest_trade import AIBacktestTrade
from app.tasks import celery_app
from app.utils.ai_market_analyzer import AIMarketAnalyzer
from app.utils.decision_executor import DecisionExecutor

logger = logging.getLogger(__name__)

# 预热数据量
PREHEAT_COUNT = 300


class AIBacktestContext:
    """AI 回测运行时上下文。"""

    def __init__(self, backtest_id: str, config: dict):
        self.backtest_id = backtest_id
        self.strategy_id = config["strategy_id"]
        self.symbol = config["symbol"]
        self.timeframe = config["timeframe"]
        self.start_time = config["start_time"]
        self.total_klines = config["total_klines"]
        self.initial_capital = float(config["initial_capital"])
        self.fee_rate = float(config["fee_rate"])
        self.use_ai = config["use_ai"]

        # 运行时状态
        self.current_equity = self.initial_capital
        self.available_cash = self.initial_capital
        self.current_position: Optional[Dict[str, Any]] = None
        self.current_trade: Optional[Dict] = None
        self.completed_trades: List[Dict] = []
        self.current_kline_index = 0
        self.total_trades = 0
        self.ai_call_count = 0
        self.ai_fail_count = 0
        self.use_ai_real = config["use_ai"]

        # 策略规则
        self.strategy_rules = config.get("strategy_rules", {})

        # 全部 K 线数据（预热 + 回测区间）
        self.all_klines: List[Dict] = []
        self.preheat_count = PREHEAT_COUNT


@celery_app.task(bind=True, max_retries=0, acks_late=True)
def run_ai_backtest(self, backtest_id: str):
    """执行 AI 回测（核心入口）。"""
    logger.info(f"AI backtest {backtest_id} started")

    try:
        asyncio.run(_run_backtest_async(backtest_id))
    except Exception as e:
        logger.exception(f"AI backtest {backtest_id} failed: {e}")
        _publish_progress(backtest_id, "error", 0, 0, 0, 0, message=str(e))
        # 更新数据库状态为失败
        asyncio.run(_update_status_failed(backtest_id, str(e)))


async def _make_local_session_maker():
    """在子进程当前事件循环中创建全新的引擎和 session maker。

    Celery prefork 模式下，模块级 async_session_maker 的引擎在父进程
    事件循环中创建，子进程 fork 后继承的引擎绑定了父进程的循环。直接
    使用会导致 asyncpg 的 "Future attached to a different loop" 错误。
    """
    from app.core.database import _build_engine_kwargs
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    engine = create_async_engine(**_build_engine_kwargs())
    return engine, async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


async def _run_backtest_async(backtest_id: str):
    """异步执行回测主逻辑。"""
    local_engine, local_session_maker = await _make_local_session_maker()
    try:
        async with local_session_maker() as session:
            # 1. 加载配置
            from sqlalchemy import select

            result = await session.execute(
                select(AIBacktest).where(AIBacktest.id == backtest_id)
            )
            backtest = result.scalar_one_or_none()
            if not backtest:
                logger.error(f"AI backtest {backtest_id} not found")
                return

            # 更新状态为 running
            backtest.status = "running"
            backtest.started_at = datetime.now(timezone.utc)
            await session.commit()

            # 构建上下文
            config = {
                "strategy_id": str(backtest.strategy_id),
                "symbol": backtest.symbol,
                "timeframe": backtest.timeframe,
                "start_time": backtest.start_time,
                "total_klines": backtest.total_klines,
                "initial_capital": float(backtest.initial_capital),
                "fee_rate": float(backtest.fee_rate),
                "use_ai": backtest.use_ai,
                "strategy_rules": backtest.strategy.rules if backtest.strategy else {},
            }
            ctx = AIBacktestContext(backtest_id, config)

        # 2. 预热阶段
        _publish_progress(backtest_id, "preheat", 2, 0, ctx.total_klines, 0,
                          message="正在获取预热数据...")
        preheat_klines = _fetch_klines(ctx.symbol, ctx.timeframe, ctx.start_time, PREHEAT_COUNT)
        ctx.preheat_count = len(preheat_klines)

        # 3. 拉取回测区间数据
        _publish_progress(backtest_id, "preheat", 5, 0, ctx.total_klines, 0,
                          message="正在拉取回测区间 K 线数据...")
        backtest_klines = _fetch_backtest_klines(ctx)
        ctx.all_klines = preheat_klines + backtest_klines

        # 4. 逐根推进主循环
        analyzer = AIMarketAnalyzer(session_maker=local_session_maker)
        executor = DecisionExecutor(ctx)

        for idx, kline in enumerate(backtest_klines):
            ctx.current_kline_index = idx + 1
            kline_data = ctx.all_klines[:ctx.preheat_count + idx + 1]

            # 计算技术指标
            indicators = _calculate_indicators(kline_data)

            # AI 分析（或规则引擎）
            ai_result = None
            if ctx.use_ai_real:
                try:
                    ai_result = await analyzer.analyze(
                        symbol=ctx.symbol,
                        timeframe=ctx.timeframe,
                        kline=kline,
                        indicators=indicators,
                        position=ctx.current_position,
                        strategy_rules=ctx.strategy_rules,
                        account_status={
                            "initial_capital": ctx.initial_capital,
                            "current_equity": ctx.current_equity,
                            "available_cash": ctx.available_cash,
                        },
                        current_kline_index=idx + 1,
                        total_klines=ctx.total_klines,
                    )
                    ctx.ai_call_count += 1
                    ctx.ai_fail_count = 0
                except Exception as e:
                    ctx.ai_fail_count += 1
                    logger.warning(f"AI call failed at kline {idx+1}: {e}")
                    if ctx.ai_fail_count >= 3:
                        ctx.use_ai_real = False
                        logger.warning("AI 连续失败 3 次，降级为规则引擎")

            # 执行决策
            executor.execute(kline, ai_result, indicators)

            # 更新进度（每 10 根或最后 10 根每根都推）
            if idx % 10 == 0 or idx >= ctx.total_klines - 10:
                progress = 5 + int((idx + 1) / ctx.total_klines * 90)
                _publish_progress(
                    backtest_id, "running", progress,
                    idx + 1, ctx.total_klines, ctx.total_trades,
                    current_position=ctx.current_position,
                    message=f"正在推进第 {idx+1}/{ctx.total_klines} 根 K 线",
                )

        # 5. 生成总结
        _publish_progress(backtest_id, "summary", 98, ctx.total_klines, ctx.total_klines,
                          ctx.total_trades, message="正在生成总结报告...")
        summary = _calculate_summary(ctx)

        # 6. 保存交易记录到数据库（使用本地 session maker）
        async with local_session_maker() as session:
            backtest = (await session.execute(
                select(AIBacktest).where(AIBacktest.id == backtest_id)
            )).scalar_one()

            # 保存交易明细
            for t in ctx.completed_trades:
                # 转换时间戳毫秒 -> datetime
                _entry_time = t.get("entry_time")
                if isinstance(_entry_time, (int, float)):
                    _entry_time = datetime.fromtimestamp(_entry_time / 1000, tz=timezone.utc)
                _exit_time = t.get("exit_time")
                if isinstance(_exit_time, (int, float)):
                    _exit_time = datetime.fromtimestamp(_exit_time / 1000, tz=timezone.utc)

                trade = AIBacktestTrade(
                    backtest_id=backtest.id,
                    index=t["index"],
                    direction=t["direction"],
                    entry_time=_entry_time,
                    entry_price=t["entry_price"],
                    quantity=t["quantity"],
                    open_ai_analysis=t.get("open_ai_analysis"),
                    open_reason=t.get("open_reason"),
                    open_confidence=t.get("open_confidence"),
                    stop_loss=t.get("stop_loss"),
                    take_profit=t.get("take_profit"),
                    exit_time=_exit_time,
                    exit_price=t.get("exit_price"),
                    exit_reason=t.get("exit_reason"),
                    exit_ai_analysis=t.get("exit_ai_analysis"),
                    exit_confidence=t.get("exit_confidence"),
                    holding_bars=t.get("holding_bars"),
                    pnl=t.get("pnl"),
                    pnl_pct=t.get("pnl_pct"),
                    fee=t.get("fee"),
                    extra=t.get("extra"),
                )
                session.add(trade)

            # 更新回测记录
            backtest.status = "completed"
            backtest.completed_klines = ctx.total_klines
            backtest.completed_at = datetime.now(timezone.utc)
            backtest.result_summary = summary
            await session.commit()

        # 7. 推送完成事件
        _publish_progress(backtest_id, "done", 100, ctx.total_klines, ctx.total_klines,
                          ctx.total_trades, message="回测完成")

        logger.info(f"AI backtest {backtest_id} completed: {ctx.total_trades} trades")
    finally:
        await local_engine.dispose()


async def _update_status_failed(backtest_id: str, error: str):
    """更新回测状态为失败。"""
    _, local_session_maker = await _make_local_session_maker()
    async with local_session_maker() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(AIBacktest).where(AIBacktest.id == backtest_id)
        )
        bt = result.scalar_one_or_none()
        if bt:
            bt.status = "failed"
            bt.completed_at = datetime.now(timezone.utc)
            bt.result_summary = {"error": error}
            await session.commit()


def _publish_progress(
    backtest_id: str, stage: str, progress: float,
    current_kline: int, total_klines: int, current_trades: int,
    current_position: Optional[dict] = None, message: str = "",
):
    """推送进度到 Redis Pub/Sub。

    使用 settings.REDIS_URL 直接创建同步 Redis 连接，
    避免依赖模块级 async redis_client（Celery 子进程中可能不可用）。
    """
    try:
        from app.core.config import settings
        import redis as sync_redis

        payload = {
            "backtest_id": backtest_id,
            "stage": stage,
            "progress": progress,
            "current_kline": current_kline,
            "total_klines": total_klines,
            "current_trades": current_trades,
            "current_position": current_position,
            "message": message,
        }
        channel = f"ai-backtest-progress:{backtest_id}"
        r = sync_redis.from_url(settings.REDIS_URL)
        r.publish(channel, json.dumps(payload, ensure_ascii=False))
        r.close()
    except Exception as e:
        logger.warning(f"Failed to publish progress: {e}")


def _fetch_klines(symbol: str, timeframe: str, since: datetime, limit: int) -> List[Dict]:
    """获取历史 K 线数据（同步调用 CCXT）。"""
    import ccxt
    from app.core.config import settings

    exchange = ccxt.binance({
        "enableRateLimit": True,
        "proxies": {"https": settings.EXCHANGE_PROXY, "http": settings.EXCHANGE_PROXY}
        if settings.EXCHANGE_PROXY else None,
    })
    since_ts = int(since.timestamp() * 1000)
    raw = exchange.fetch_ohlcv(symbol, timeframe, since=since_ts, limit=limit)
    return [
        {
            "timestamp": int(r[0]),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        }
        for r in raw
    ]


def _fetch_backtest_klines(ctx: AIBacktestContext) -> List[Dict]:
    """拉取回测区间全部 K 线。"""
    return _fetch_klines(ctx.symbol, ctx.timeframe, ctx.start_time, ctx.total_klines)


def _calculate_indicators(klines: List[Dict]) -> Dict[str, Any]:
    """计算技术指标。"""
    closes = np.array([k["close"] for k in klines])
    highs = np.array([k["high"] for k in klines])
    lows = np.array([k["low"] for k in klines])

    n = len(closes)
    indicators = {}

    # MA
    indicators["ma5"] = float(np.mean(closes[-5:])) if n >= 5 else closes[-1]
    indicators["ma10"] = float(np.mean(closes[-10:])) if n >= 10 else closes[-1]
    indicators["ma20"] = float(np.mean(closes[-20:])) if n >= 20 else closes[-1]

    # RSI
    if n >= 15:
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        indicators["rsi_14"] = float(rsi)
    else:
        indicators["rsi_14"] = 50.0

    # 关键水平
    indicators["support"] = [float(np.min(lows[-20:]))] if n >= 20 else [float(np.min(lows))]
    indicators["resistance"] = [float(np.max(highs[-20:]))] if n >= 20 else [float(np.max(highs))]

    return indicators


def _calculate_summary(ctx: AIBacktestContext) -> Dict[str, Any]:
    """计算回测总结指标。"""
    trades = ctx.completed_trades
    if not trades:
        return {
            "total_trades": 0,
            "total_pnl": 0.0,
            "total_return_pct": 0.0,
            "win_rate": 0.0,
            "final_equity": ctx.current_equity,
            "ai_calls": ctx.ai_call_count,
            "open_count": 0,
            "close_reasons": {},
        }

    total_pnl = sum(t["pnl"] for t in trades)
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]

    win_rate = len(wins) / len(trades) * 100

    # 最大回撤
    equities = [ctx.initial_capital]
    for t in trades:
        equities.append(equities[-1] + t["pnl"])
    peak = equities[0]
    max_drawdown = 0.0
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_drawdown:
            max_drawdown = dd

    # 平仓原因分布
    close_reasons = {}
    for t in trades:
        reason = t.get("exit_reason", "unknown")
        close_reasons[reason] = close_reasons.get(reason, 0) + 1

    return {
        "total_trades": len(trades),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_pnl / ctx.initial_capital * 100, 2),
        "win_rate": round(win_rate, 2),
        "max_single_profit": round(max(t["pnl"] for t in wins), 2) if wins else 0.0,
        "max_single_loss": round(min(t["pnl"] for t in losses), 2) if losses else 0.0,
        "avg_pnl": round(total_pnl / len(trades), 2),
        "max_consecutive_wins": _max_consecutive(trades, lambda t: t["pnl"] > 0),
        "max_consecutive_losses": _max_consecutive(trades, lambda t: t["pnl"] <= 0),
        "max_drawdown_pct": round(max_drawdown, 2),
        "final_equity": round(ctx.current_equity, 2),
        "total_fee": round(sum(t["fee"] for t in trades), 2),
        "avg_holding_bars": round(np.mean([t["holding_bars"] for t in trades]), 1),
        "ai_calls": ctx.ai_call_count,
        "open_count": len(trades),
        "close_reasons": close_reasons,
    }


def _max_consecutive(trades, predicate):
    """计算最大连续次数。"""
    max_count = 0
    current = 0
    for t in trades:
        if predicate(t):
            current += 1
            max_count = max(max_count, current)
        else:
            current = 0
    return max_count