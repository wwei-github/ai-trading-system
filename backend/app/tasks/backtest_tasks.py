"""回测任务。

由 StrategyService.create_backtest 派发，负责：
1. 加载回测记录与策略
2. 通过 CCXT 公开接口拉取历史 K 线
3. 执行简化版回测（SMA 交叉策略 / buy-and-hold 基线）
4. 计算回测指标：总收益率、最大回撤、夏普比率、胜率、交易次数
5. 将结果写入 backtests 表
"""

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from app.tasks import celery_app


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

    # 公开接口无需凭证
    client = CCXTClient(
        exchange=exchange,
        api_key="",
        api_secret="",
    )
    try:
        await client.load_markets()
        # CCXT 一次最多 1000 根，循环拉取
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
        # 按时间过滤
        df = df[
            (df["timestamp"] >= pd.Timestamp(since_ms, unit="ms", tz="UTC"))
            & (df["timestamp"] <= pd.Timestamp(end_ms, unit="ms", tz="UTC"))
        ]
        return df.reset_index(drop=True)
    finally:
        await client.close()


def _run_sma_backtest(
    df: pd.DataFrame,
    initial_capital: float,
    fast_period: int = 7,
    slow_period: int = 25,
) -> Dict[str, Any]:
    """执行 SMA 交叉策略回测。

    快线上穿慢线买入，快线下穿慢线卖出（全仓进出）。
    """
    if len(df) < slow_period + 1:
        return _run_buy_hold(df, initial_capital)

    df = df.copy()
    df["sma_fast"] = df["close"].rolling(fast_period).mean()
    df["sma_slow"] = df["close"].rolling(slow_period).mean()

    # 信号：1 持仓 / 0 空仓
    df["signal"] = 0
    df.loc[
        df["sma_fast"] > df["sma_slow"], "signal"
    ] = 1
    df["signal"] = df["signal"].shift(1).fillna(0)

    # 收益率
    df["ret"] = df["close"].pct_change().fillna(0)
    df["strategy_ret"] = df["signal"] * df["ret"]

    # 净值
    df["nav"] = (1 + df["strategy_ret"]).cumprod() * initial_capital
    df["buy_hold_nav"] = (1 + df["ret"]).cumprod() * initial_capital

    # 交易次数（信号变化）
    trades = (df["signal"].diff().abs() > 0).sum()

    return _build_metrics(
        df, initial_capital, trades, df["buy_hold_nav"].iloc[-1]
    )


def _run_buy_hold(
    df: pd.DataFrame, initial_capital: float
) -> Dict[str, Any]:
    """buy-and-hold 基线回测。"""
    df = df.copy()
    df["ret"] = df["close"].pct_change().fillna(0)
    df["nav"] = (1 + df["ret"]).cumprod() * initial_capital
    trades = 1 if len(df) > 0 else 0
    final_bh = df["nav"].iloc[-1] if len(df) > 0 else initial_capital
    return _build_metrics(df, initial_capital, trades, final_bh)


def _build_metrics(
    df: pd.DataFrame,
    initial_capital: float,
    trades: int,
    buy_hold_final: float,
) -> Dict[str, Any]:
    """汇总回测指标。"""
    if len(df) == 0:
        return {
            "total_return": 0.0,
            "final_value": initial_capital,
            "buy_hold_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "volatility": 0.0,
            "trades": 0,
            "bars": 0,
        }

    final_value = float(df["nav"].iloc[-1])
    total_return = (final_value - initial_capital) / initial_capital
    buy_hold_return = (buy_hold_final - initial_capital) / initial_capital

    # 最大回撤
    nav = df["nav"].values
    peak = np.maximum.accumulate(nav)
    drawdown = (nav - peak) / peak
    max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0.0

    # 夏普比率（按日年化简化处理）
    returns = df["strategy_ret"].values if "strategy_ret" in df else df["ret"].values
    if len(returns) > 1 and returns.std() > 0:
        sharpe = float(returns.mean() / returns.std() * np.sqrt(252))
    else:
        sharpe = 0.0
    volatility = float(returns.std() * np.sqrt(252)) if len(returns) > 0 else 0.0

    return {
        "total_return": float(total_return),
        "final_value": float(final_value),
        "buy_hold_return": float(buy_hold_return),
        "max_drawdown": float(max_drawdown),
        "sharpe_ratio": float(sharpe),
        "volatility": float(volatility),
        "trades": int(trades),
        "bars": int(len(df)),
        "start_price": float(df["close"].iloc[0]),
        "end_price": float(df["close"].iloc[-1]),
    }


async def _run_backtest_async(backtest_id: str) -> dict:
    """异步执行回测。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.backtest import Backtest
    from app.models.strategy import Strategy
    from app.services.strategy_service import StrategyService

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

        try:
            # 加载策略
            strat_result = await session.execute(
                select(Strategy).where(Strategy.id == backtest.strategy_id)
            )
            strategy = strat_result.scalar_one_or_none()

            # 时间范围转毫秒
            since_ms = int(
                datetime.combine(
                    backtest.start_date, datetime.min.time(), tzinfo=timezone.utc
                ).timestamp()
                * 1000
            )
            end_ms = int(
                datetime.combine(
                    backtest.end_date, datetime.min.time(), tzinfo=timezone.utc
                ).timestamp()
                * 1000
            )

            logger.info(
                "开始回测 | backtest_id={} symbol={} timeframe={} range={}~{}",
                backtest_id,
                backtest.symbol,
                backtest.timeframe,
                backtest.start_date,
                backtest.end_date,
            )

            # 拉取 K 线
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
                return {
                    "backtest_id": backtest_id,
                    "status": "failed",
                    "reason": "no_data",
                }

            initial_capital = float(backtest.initial_capital)

            # 合并策略参数与回测参数
            params: Dict[str, Any] = {}
            if strategy and strategy.params:
                params.update(strategy.params)
            if backtest.params:
                params.update(backtest.params)

            fast_period = int(params.get("fast_period", 7))
            slow_period = int(params.get("slow_period", 25))

            # 执行回测
            if params.get("strategy_type") == "buy_hold" or slow_period >= len(df):
                metrics = _run_buy_hold(df, initial_capital)
            else:
                metrics = _run_sma_backtest(
                    df, initial_capital, fast_period, slow_period
                )

            # 保存结果
            service = StrategyService(session)
            await service.update_backtest_result(
                bt_uuid, {"metrics": metrics, "params": params}, status="completed"
            )
            await session.commit()

            logger.info("回测完成 | backtest_id={} 收益={:.2%}", backtest_id, metrics["total_return"])
            return {
                "backtest_id": backtest_id,
                "status": "completed",
                "metrics": metrics,
            }
        except Exception as e:
            logger.exception("回测失败 | backtest_id={}", backtest_id)
            backtest.status = "failed"
            backtest.result = {"reason": str(e)}
            await session.commit()
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
