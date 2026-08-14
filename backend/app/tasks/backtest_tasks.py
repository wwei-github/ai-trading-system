"""回测任务（Stage 6.4，对齐 PRD §5.6.3 R1）。

由 StrategyService.create_backtest 派发，负责：
1. 加载回测记录与策略
2. 通过 CCXT 公开接口拉取历史 K 线（或从 DB klines 表读取）
3. 调用 backtest_engine 执行向量化回测
4. 计算回测指标：总收益率、年化、最大回撤、夏普、Sortino、胜率、盈亏比
5. 将结果写入 backtests 表 + backtest_trades 明细表
6. 通过 Redis 发布进度（供 SSE 订阅）
"""

import asyncio
import datetime
import json
import uuid
from datetime import timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from app.tasks import celery_app
from app.core.database import redis_client


# ---------- 进度发布 ----------

async def _publish_progress(backtest_id: str, stage: str, progress: int, message: str = ""):
    """通过 Redis 发布回测进度（供 SSE 订阅）。"""
    try:
        if redis_client is None:
            return
        channel = f"backtest:progress:{backtest_id}"
        payload = {
            "backtest_id": backtest_id,
            "stage": stage,  # init / fetching / running / saving / done / error
            "progress": progress,  # 0-100
            "message": message,
            "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
        }
        await redis_client.publish(channel, json.dumps(payload))
    except Exception as e:
        logger.warning("发布回测进度失败 | {} {}", backtest_id, e)


# ---------- K 线拉取 ----------

async def _fetch_ohlcv(
    symbol: str,
    timeframe: str,
    since_ms: int,
    end_ms: int,
    exchange: str = "binance",
) -> pd.DataFrame:
    """通过 CCXT 公开接口拉取历史 K 线。

    Returns:
        DataFrame，列：timestamp(open) / open / high / low / close / volume
    """
    from app.exchange.ccxt_client import CCXTClient

    client = CCXTClient(exchange=exchange, api_key="", api_secret="")
    try:
        await client.load_markets()
        all_ohlcv: List[List[Any]] = []
        cur = since_ms
        while cur < end_ms:
            batch = await client.fetch_ohlcv(
                symbol, timeframe=timeframe, since=cur, limit=1000
            )
            if not batch:
                break
            all_ohlcv.extend(batch)
            last_ts = batch[-1][0]
            if last_ts <= cur:
                break
            cur = last_ts + 1
            if len(batch) < 1000:
                break

        if not all_ohlcv:
            return pd.DataFrame()

        df = pd.DataFrame(
            all_ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        df = df[
            (df["timestamp"] >= pd.Timestamp(since_ms, unit="ms", tz="UTC"))
            & (df["timestamp"] <= pd.Timestamp(end_ms, unit="ms", tz="UTC"))
        ]
        return df.reset_index(drop=True)
    finally:
        await client.close()


# ---------- 策略类型识别 ----------

def _detect_strategy_type(strategy, params: Dict[str, Any]) -> str:
    """从策略参数或 category 推断回测引擎使用的策略类型。"""
    # 显式指定优先
    st = params.get("strategy_type")
    if st:
        return st
    # 从模板策略 ID 推断
    from app.schemas.strategy_dsl import TEMPLATE_STRATEGY_IDS
    if strategy and str(strategy.id) == TEMPLATE_STRATEGY_IDS["double_ma"]:
        return "double_ma"
    if strategy and str(strategy.id) == TEMPLATE_STRATEGY_IDS["rsi_reversal"]:
        return "rsi_reversal"
    if strategy and str(strategy.id) == TEMPLATE_STRATEGY_IDS["turtle_breakout"]:
        return "turtle_breakout"
    # 从 category 推断
    if strategy:
        cat = (strategy.category or "").lower()
        if "trend" in cat or "ma" in cat:
            return "double_ma"
        if "mean_reversion" in cat or "rsi" in cat:
            return "rsi_reversal"
        if "breakout" in cat or "turtle" in cat:
            return "turtle_breakout"
    # 默认双均线
    return "double_ma"


# ---------- 异步回测主流程 ----------

async def _run_backtest_async(backtest_id: str) -> dict:
    """异步执行回测。"""
    from sqlalchemy import select, delete

    from app.core.database import async_session_maker
    from app.models.backtest import Backtest
    from app.models.backtest_trade import BacktestTrade
    from app.models.strategy import Strategy
    from app.utils.backtest_engine import run_backtest

    bt_uuid = uuid.UUID(backtest_id)
    async with async_session_maker() as session:
        result = await session.execute(
            select(Backtest).where(Backtest.id == bt_uuid)
        )
        backtest = result.scalar_one_or_none()
        if backtest is None:
            logger.error("回测不存在: {}", backtest_id)
            return {"backtest_id": backtest_id, "status": "failed", "reason": "not_found"}

        # 更新状态为 running
        backtest.status = "running"
        await session.commit()
        await _publish_progress(backtest_id, "init", 5, "初始化回测")

        try:
            # 加载策略
            strat_result = await session.execute(
                select(Strategy).where(Strategy.id == backtest.strategy_id)
            )
            strategy = strat_result.scalar_one_or_none()

            # 时间范围转毫秒
            since_ms = int(
                datetime.datetime.combine(
                    backtest.start_date, datetime.time.min, tzinfo=timezone.utc
                ).timestamp()
                * 1000
            )
            end_ms = int(
                datetime.datetime.combine(
                    backtest.end_date, datetime.time.min, tzinfo=timezone.utc
                ).timestamp()
                * 1000
            )

            logger.info(
                "开始回测 | backtest_id={} symbol={} timeframe={} range={}~{}",
                backtest_id, backtest.symbol, backtest.timeframe,
                backtest.start_date, backtest.end_date,
            )

            # 拉取 K 线
            await _publish_progress(backtest_id, "fetching", 15, "拉取历史 K 线")
            df = await _fetch_ohlcv(
                symbol=backtest.symbol,
                timeframe=backtest.timeframe,
                since_ms=since_ms,
                end_ms=end_ms,
            )

            if df.empty:
                backtest.status = "failed"
                backtest.result = {"reason": "no_data", "bars": 0}
                await session.commit()
                await _publish_progress(backtest_id, "error", 100, "无 K 线数据")
                return {"backtest_id": backtest_id, "status": "failed", "reason": "no_data"}

            await _publish_progress(backtest_id, "fetching", 30, f"已拉取 {len(df)} 根 K 线")

            # 合并策略参数与回测参数
            params: Dict[str, Any] = {}
            if strategy and strategy.params:
                params.update(strategy.params)
            if backtest.params:
                params.update(backtest.params)

            # 识别策略类型
            strategy_type = _detect_strategy_type(strategy, params)

            # 风控参数
            risk_control = {}
            if strategy and strategy.rules:
                rc = strategy.rules.get("risk_control", {})
                if rc:
                    risk_control = rc

            # 执行回测
            await _publish_progress(backtest_id, "running", 50, f"执行回测（{strategy_type}）")
            bt_result = run_backtest(
                df=df,
                strategy_type=strategy_type,
                params=params,
                initial_capital=float(backtest.initial_capital),
                fee_rate=float(params.get("fee_rate", 0.001)),
                slippage=float(params.get("slippage", 0.0)),
                risk_control=risk_control,
            )

            await _publish_progress(backtest_id, "saving", 80, "保存回测结果")

            # 清除旧明细（重跑场景）
            await session.execute(
                delete(BacktestTrade).where(BacktestTrade.backtest_id == bt_uuid)
            )

            # 写入交易明细
            for trade_data in bt_result.trades:
                trade = BacktestTrade(
                    backtest_id=bt_uuid,
                    strategy_id=backtest.strategy_id,
                    side=trade_data.get("side", "long"),
                    entry_time=datetime.datetime.fromisoformat(
                        trade_data["entry_time"].replace("Z", "+00:00")
                    ) if isinstance(trade_data["entry_time"], str) else trade_data["entry_time"],
                    entry_price=trade_data["entry_price"],
                    quantity=trade_data["quantity"],
                    exit_time=datetime.datetime.fromisoformat(
                        trade_data["exit_time"].replace("Z", "+00:00")
                    ) if isinstance(trade_data["exit_time"], str) else trade_data["exit_time"],
                    exit_price=trade_data.get("exit_price"),
                    pnl=trade_data.get("pnl", 0),
                    pnl_pct=trade_data.get("pnl_pct", 0),
                    holding_bars=trade_data.get("holding_bars", 0),
                    exit_reason=trade_data.get("exit_reason", "signal"),
                    symbol=backtest.symbol,
                )
                session.add(trade)

            # 保存结果
            backtest.status = "completed"
            backtest.result = bt_result.to_dict()
            await session.commit()

            await _publish_progress(
                backtest_id, "done", 100,
                f"回测完成：{bt_result.metrics.trade_count} 笔交易，收益 {bt_result.metrics.total_return:.2%}"
            )

            logger.info(
                "回测完成 | backtest_id={} 收益={:.2%} 回撤={:.2%} 夏普={:.2f}",
                backtest_id, bt_result.metrics.total_return,
                bt_result.metrics.max_drawdown, bt_result.metrics.sharpe_ratio,
            )
            return {
                "backtest_id": backtest_id,
                "status": "completed",
                "metrics": bt_result.metrics.to_dict(),
            }
        except Exception as e:
            logger.exception("回测失败 | backtest_id={}", backtest_id)
            backtest.status = "failed"
            backtest.result = {"reason": str(e)}
            await session.commit()
            await _publish_progress(backtest_id, "error", 100, f"回测失败: {str(e)}")
            return {"backtest_id": backtest_id, "status": "failed", "reason": str(e)}


@celery_app.task(name="run_backtest", bind=True)
def run_backtest(self, backtest_id: str) -> dict:
    """执行策略回测。

    Args:
        backtest_id: 回测记录 ID（字符串形式 UUID）

    Returns:
        回测结果字典
    """
    logger.info("开始回测任务 | backtest_id={} task_id={}", backtest_id, self.request.id)
    return asyncio.run(_run_backtest_async(backtest_id))
