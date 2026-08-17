"""AI 回测 Celery 异步任务。"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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
        # 多策略规则（用于多策略回测时参考多个策略）
        self.multi_strategy_rules: List[dict] = config.get("multi_strategy_rules", [])

        # 全部 K 线数据（预热 + 回测区间）
        self.all_klines: List[Dict] = []
        self.preheat_count = PREHEAT_COUNT

        # ========== 08-AI回测K线分析优化 新增字段 ==========
        # 持仓免分析状态
        self.ai_analysis_paused: bool = False

        # 两级 AI 过滤统计
        self.precheck_total: int = 0
        self.precheck_triggered: int = 0

        # 最后一次 AI 分析窗口信息
        self.last_ai_kline_window: Optional[Tuple[int, int]] = None
        self.last_trigger_reason: Optional[str] = None

        # 本地模型预筛配置
        self.use_local_model: bool = config.get("use_local_model", False)
        self.local_model_klines: int = config.get("local_model_klines", 10)

        # 关键位（从初始化分析或深度分析中提取）
        self.key_levels: List[Dict] = []
        self.initial_analysis: Dict = {}


def _check_stop_signal(backtest_id: str) -> bool:
    """检查是否收到停止信号。"""
    try:
        from app.core.config import settings
        import redis as sync_redis
        r = sync_redis.from_url(settings.REDIS_URL)
        stop_key = f"stop:ai-backtest:{backtest_id}"
        result = r.get(stop_key)
        r.close()
        return result is not None
    except Exception:
        return False


# ========== 08-AI回测K线分析优化 新增辅助函数 ==========

KEY_LEVEL_THRESHOLD_PCT = 0.005  # 0.5% 阈值


def _check_key_level_hit(kline: Dict, key_levels: List[Dict]) -> Optional[Dict]:
    """检测 K 线是否命中关键位（±0.5% 范围）。

    Returns: 命中的关键位信息，未命中返回 None
    """
    close = kline["close"]
    high = kline["high"]
    low = kline["low"]
    for level in key_levels:
        price = level["price"]
        delta = price * KEY_LEVEL_THRESHOLD_PCT
        # 只要 K 线的价格区间 [low, high] 与 [price-delta, price+delta] 相交
        if high >= (price - delta) and low <= (price + delta):
            return {
                **level,
                "hit_price": close,
                "distance_pct": abs(close - price) / price * 100,
            }
    return None


def _append_analysis_log(ctx: AIBacktestContext, kline_index: int,
                          trigger: str, analysis: Dict) -> None:
    """追加深度分析日志到上下文（保存完整分析数据供前端展示）。"""
    if not hasattr(ctx, "_analysis_logs"):
        ctx._analysis_logs = []
    _ma = analysis.get("market_analysis") or {}
    _tp = analysis.get("trade_plan") or {}
    log_entry = {
        "kline_index": kline_index,
        "trigger": ctx.last_trigger_reason or trigger,
        "trigger_reason": ctx.last_trigger_reason or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis": {
            "trend": _ma.get("trend"),
            "key_levels": analysis.get("key_levels", ctx.key_levels),
            "decision": analysis.get("decision"),
            "confidence": _tp.get("confidence"),
            "reasoning": _tp.get("reason") or _ma.get("summary") or "",
            "summary": _ma.get("summary", ""),
            "stop_loss": _tp.get("stop_loss"),
            "take_profit": _tp.get("take_profit"),
            "stop_loss_method": _tp.get("stop_loss_method", ""),
            "risk_reward_ratio": _tp.get("risk_reward_ratio"),
        },
    }
    ctx._analysis_logs.append(log_entry)


def _append_trade_opened_log(ctx: AIBacktestContext, kline_index: int) -> None:
    """记录开单日志（含仓位、止盈止损详情）。"""
    trade = ctx.current_trade
    if not trade:
        return
    if not hasattr(ctx, "_analysis_logs"):
        ctx._analysis_logs = []
    # 计算盈亏比
    risk_reward = None
    if trade.get("stop_loss") and trade.get("take_profit") and trade.get("entry_price"):
        entry = trade["entry_price"]
        if trade["direction"] == "long":
            risk = entry - trade["stop_loss"]
            reward = trade["take_profit"] - entry
        else:
            risk = trade["stop_loss"] - entry
            reward = entry - trade["take_profit"]
        if risk > 0:
            risk_reward = round(reward / risk, 2)

    log_entry = {
        "kline_index": kline_index,
        "trigger": "trade_opened",
        "trigger_reason": trade.get("open_reason", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis": {},
        "skipped": False,
        "trade_info": {
            "type": "opened",
            "direction": trade["direction"],
            "entry_price": trade["entry_price"],
            "quantity": trade["quantity"],
            "stop_loss": trade.get("stop_loss"),
            "take_profit": trade.get("take_profit"),
            "open_confidence": trade.get("open_confidence"),
            "risk_reward_ratio": risk_reward,
            "source_strategy": trade.get("source_strategy", ""),
        },
    }
    ctx._analysis_logs.append(log_entry)


def _append_trade_closed_log(ctx: AIBacktestContext, kline_index: int) -> None:
    """记录平仓日志（含盈亏结果）。"""
    if not ctx.completed_trades:
        return
    trade = ctx.completed_trades[-1]
    if not hasattr(ctx, "_analysis_logs"):
        ctx._analysis_logs = []
    log_entry = {
        "kline_index": kline_index,
        "trigger": "trade_closed",
        "trigger_reason": trade.get("exit_reason", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis": {},
        "skipped": False,
        "trade_info": {
            "type": "closed",
            "direction": trade["direction"],
            "entry_price": trade["entry_price"],
            "exit_price": trade.get("exit_price"),
            "quantity": trade["quantity"],
            "pnl": trade.get("pnl"),
            "pnl_pct": trade.get("pnl_pct"),
            "holding_bars": trade.get("holding_bars"),
            "exit_reason": trade.get("exit_reason"),
        },
    }
    ctx._analysis_logs.append(log_entry)


def _append_skip_log(ctx: AIBacktestContext, kline_index: int,
                      skip_reason: str, had_position: bool = False) -> None:
    """记录跳过 AI 分析的 K 线日志（每根 K 线都有记录）。"""
    if not hasattr(ctx, "_analysis_logs"):
        ctx._analysis_logs = []
    log_entry = {
        "kline_index": kline_index,
        "trigger": "skipped",
        "trigger_reason": skip_reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis": {},
        "skipped": True,
        "had_position": had_position,
    }
    ctx._analysis_logs.append(log_entry)


def _append_precheck_log(ctx: AIBacktestContext, kline_index: int,
                          raw_response: str) -> None:
    """记录预筛通过日志（展示预筛 AI 的原始分析结果）。"""
    if not hasattr(ctx, "_analysis_logs"):
        ctx._analysis_logs = []
    # 尝试提取 JSON 中的 summary 字段
    summary = ""
    try:
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(raw_response[start:end + 1])
            summary = parsed.get("summary", raw_response[:200])
        else:
            summary = raw_response[:200]
    except Exception:
        summary = raw_response[:200]

    log_entry = {
        "kline_index": kline_index,
        "trigger": "precheck_pass",
        "trigger_reason": "预筛通过，即将进入深度分析",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis": {
            "summary": summary,
            "reasoning": raw_response,
        },
        "skipped": False,
        "precheck": True,
    }
    ctx._analysis_logs.append(log_entry)


@celery_app.task(bind=True, max_retries=0, acks_late=True)
def cleanup_stale_pending_backtests(self):
    """定时清理队列中超过 30 分钟未消费的 pending 回测任务。

    由 Celery Beat 每 5 分钟触发一次。
    """
    logger.info("Checking stale pending backtests...")
    try:
        asyncio.run(_cleanup_stale_pending())
    except Exception as e:
        logger.exception(f"Cleanup stale pending backtests failed: {e}")


async def _cleanup_stale_pending():
    """查询并取消所有超过 30 分钟的 pending 回测。"""
    from datetime import timedelta
    from sqlalchemy import select

    local_engine, local_session_maker = await _make_local_session_maker()
    try:
        async with local_session_maker() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            result = await session.execute(
                select(AIBacktest).where(
                    AIBacktest.status == "pending",
                    AIBacktest.created_at < cutoff,
                )
            )
            stale_backtests = list(result.scalars().all())

            if not stale_backtests:
                logger.info("No stale pending backtests found")
                return

            logger.warning(
                f"Found {len(stale_backtests)} stale pending backtests, cancelling..."
            )

            for bt in stale_backtests:
                bt.status = "cancelled"
                bt.completed_at = datetime.now(timezone.utc)
                bt.result_summary = {
                    "status": "cancelled",
                    "message": "队列中超时自动取消（超过30分钟未消费）",
                    "cancelled_at": datetime.now(timezone.utc).isoformat(),
                }
                logger.info(
                    f"Cancelled stale backtest {bt.id} "
                    f"(created: {bt.created_at}, age: {datetime.now(timezone.utc) - bt.created_at})"
                )

            await session.commit()

            # 尝试从 Redis 队列中移除对应的任务消息
            try:
                import redis as sync_redis
                from app.core.config import settings

                r = sync_redis.from_url(settings.REDIS_URL)
                for bt in stale_backtests:
                    bt_id = str(bt.id)
                    # 删除 Redis 中的停止标志（如果有）
                    r.delete(f"stop:ai-backtest:{bt_id}")
                    # 删除缓存进度
                    r.delete(f"ai-backtest-last-progress:{bt_id}")
                    # 推送取消事件
                    _publish_progress(
                        bt_id, "cancelled", 0, 0, bt.total_klines, 0,
                        message="队列中超时自动取消（超过30分钟未消费）",
                    )
                r.close()
            except Exception as e:
                logger.warning(f"Failed to cleanup Redis keys: {e}")

    finally:
        await local_engine.dispose()


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
    """异步执行回测主逻辑。

    严格同步约束：
    - 禁止在本函数 for 循环内部使用 asyncio.create_task / gather / ensure_future
    - 所有 AI 调用、指标计算、DB 操作必须显式 await
    - SSE progress 推送是 fire-and-forget（已封装，不阻塞）
    - 目标：AI 完整处理完 K 线 N 后，才推进到 N+1
    """
    from app.utils.ai_market_analyzer import AI_ANALYSIS_MAX_WINDOW

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

            # 构建上下文（含新增字段）
            strategy_rules = backtest.strategy.rules if backtest.strategy else {}
            multi_strategy_rules = []
            if backtest.strategy_ids:
                from app.models.strategy import Strategy
                strategies_result = await session.execute(
                    select(Strategy).where(Strategy.id.in_(backtest.strategy_ids))
                )
                multi_strategies = strategies_result.scalars().all()
                for s in multi_strategies:
                    multi_strategy_rules.append({
                        "id": str(s.id),
                        "name": s.name,
                        "category": s.category,
                        "rules": s.rules,
                    })

            config = {
                "strategy_id": str(backtest.strategy_id),
                "symbol": backtest.symbol,
                "timeframe": backtest.timeframe,
                "start_time": backtest.start_time,
                "total_klines": backtest.total_klines,
                "initial_capital": float(backtest.initial_capital),
                "fee_rate": float(backtest.fee_rate),
                "use_ai": backtest.use_ai,
                "strategy_rules": strategy_rules,
                "multi_strategy_rules": multi_strategy_rules,
                # 08-AI回测K线分析优化 新增配置
                "use_local_model": backtest.use_local_model,
                "local_model_klines": backtest.local_model_klines,
            }
            ctx = AIBacktestContext(backtest_id, config)

            # 安全兜底：AI 回测必须启用 AI 分析
            if not ctx.use_ai:
                logger.warning(f"AI backtest {backtest_id} has use_ai=False, aborting")
                backtest.status = "cancelled"
                backtest.completed_at = datetime.now(timezone.utc)
                backtest.result_summary = {
                    "message": "AI 回测未启用 AI 分析，已自动终止",
                    "status": "cancelled",
                }
                await session.commit()
                _publish_progress(backtest_id, "cancelled", 0, 0, ctx.total_klines, 0,
                                  message="AI 回测未启用 AI 分析，已自动终止")
                return

        # 2. 预热阶段
        _publish_progress(backtest_id, "preheat", 2, 0, ctx.total_klines, 0,
                          message="正在获取预热数据...")
        preheat_klines = _fetch_preheat_klines(ctx)
        ctx.preheat_count = len(preheat_klines)
        ctx.all_klines = preheat_klines  # 先只放预热数据

        # 3. 初始化 AI 分析（预热 300 根）
        analyzer = AIMarketAnalyzer(session_maker=local_session_maker)
        if ctx.use_ai_real:
            _publish_progress(backtest_id, "preheat", 3, 0, ctx.total_klines, 0,
                              message="正在分析预热数据，提取趋势和关键位...")
            try:
                initial_result = await analyzer.analyze_initial(
                    kline_window=ctx.all_klines,
                    strategy_rules=ctx.strategy_rules,
                    symbol=ctx.symbol,
                    timeframe=ctx.timeframe,
                    multi_strategy_rules=ctx.multi_strategy_rules,
                )
                ctx.initial_analysis = initial_result
                ctx.key_levels = initial_result.get("key_levels", [])
                logger.info(f"Initial analysis: trend={initial_result.get('trend')}, "
                            f"key_levels={len(ctx.key_levels)}")
            except Exception as e:
                logger.warning(f"Initial AI analysis failed: {e}")
                ctx.initial_analysis = {}
                ctx.key_levels = []

        # 4. 拉取回测区间数据
        _publish_progress(backtest_id, "preheat", 5, 0, ctx.total_klines, 0,
                          message="正在拉取回测区间 K 线数据...")
        backtest_klines = _fetch_backtest_klines(ctx)
        ctx.all_klines = preheat_klines + backtest_klines

        # 5. 初始化本地模型预筛器
        local_prechecker = None
        if ctx.use_local_model:
            try:
                from app.utils.local_model_prechecker import LocalModelPrechecker
                local_prechecker = LocalModelPrechecker(session_maker=local_session_maker)
                logger.info(f"LocalModelPrechecker initialized for backtest {backtest_id}")
            except Exception as e:
                logger.warning(f"Failed to init LocalModelPrechecker: {e}, fallback to main AI precheck")
                ctx.use_local_model = False

        # 6. 初始化执行器
        executor = DecisionExecutor(ctx)

        # 7. 逐根推进主循环
        for idx, kline in enumerate(backtest_klines):
            ctx.current_kline_index = idx + 1

            # === 停止信号检查 ===
            if _check_stop_signal(backtest_id):
                logger.info(f"AI backtest {backtest_id} received stop signal at kline {idx+1}")
                _publish_progress(backtest_id, "cancelled", 5 + int((idx + 1) / ctx.total_klines * 90),
                                  idx + 1, ctx.total_klines, ctx.total_trades,
                                  message="回测已被用户终止")
                await _save_trades_and_finalize(backtest_id, ctx, local_session_maker, "cancelled")
                return

            kline_data = ctx.all_klines[:ctx.preheat_count + idx + 1]

            # 计算技术指标
            indicators = _calculate_indicators(kline_data)

            # ========== 核心优化：两级 AI 过滤 + 持仓免分析 + 关键位检测 ==========
            ai_result = None
            had_position = ctx.current_position is not None
            should_analyze = ctx.use_ai_real

            if should_analyze:
                if had_position:
                    # 有持仓：跳过 AI 分析
                    should_analyze = False
                    ctx.ai_analysis_paused = True
                    _append_skip_log(ctx, idx + 1, "持仓中，跳过AI分析", had_position=True)
                else:
                    # 无持仓：先检查关键位命中
                    key_level_hit = _check_key_level_hit(kline, ctx.key_levels)

                    if key_level_hit is not None:
                        # 命中关键位 → 跳过预筛，直接进入深度分析
                        should_analyze = True
                        ctx.last_trigger_reason = f"key_level_hit:{key_level_hit['type']}"
                        ctx.precheck_total += 1
                        ctx.precheck_triggered += 1
                        # 记录预筛通过日志（关键位命中相当于预筛通过）
                        _append_precheck_log(ctx, idx + 1, f"命中关键位[{key_level_hit['type']}]，跳过预筛直接进入深度分析")
                        logger.debug(f"Key level hit at kline {idx+1}: {key_level_hit}")
                    else:
                        # 未命中关键位 → 走两级预筛
                        # 第一级：AI 粗略预筛（主 AI 或 本地模型）
                        precheck_passed = False
                        precheck_response = ""
                        if ctx.use_local_model and local_prechecker:
                            # 模式 B：本地模型预筛
                            # 限制最小K线数为5，单根K线太少无法判断
                            precheck_klines = max(5, ctx.local_model_klines)
                            local_window = kline_data[-min(precheck_klines, len(kline_data)):]
                            precheck_passed, precheck_response = await local_prechecker.precheck(
                                kline_window=local_window,
                                strategy_rules=ctx.strategy_rules,
                                symbol=ctx.symbol,
                                timeframe=ctx.timeframe,
                                computed_indicators=indicators,
                            )
                            ctx.last_trigger_reason = "local_model" if precheck_passed else None
                        else:
                            # 模式 A（默认）：主 AI 粗略预筛
                            # 限制最小K线数为5，单根K线太少无法判断
                            precheck_klines = max(5, ctx.local_model_klines)
                            quick_window = kline_data[-min(precheck_klines, len(kline_data)):]
                            precheck_passed, precheck_response = await analyzer.quick_precheck(
                                kline_window=quick_window,
                                strategy_rules=ctx.strategy_rules,
                                symbol=ctx.symbol,
                                timeframe=ctx.timeframe,
                                multi_strategy_rules=ctx.multi_strategy_rules,
                                computed_indicators=indicators,
                            )
                            ctx.last_trigger_reason = "ai_precheck" if precheck_passed else None

                        ctx.precheck_total += 1
                        if precheck_passed:
                            ctx.precheck_triggered += 1
                            should_analyze = True
                            # 记录预筛通过日志（含原始 AI 响应）
                            _append_precheck_log(ctx, idx + 1, precheck_response)
                        else:
                            should_analyze = False
                            _append_skip_log(ctx, idx + 1, "预筛未通过，跳过AI分析")
                            logger.debug(f"Precheck not passed at kline {idx+1}")
            else:
                # AI 已禁用（连续失败降级或配置关闭），仅处理平仓/止损
                _append_skip_log(ctx, idx + 1, "AI已降级为规则引擎，仅处理平仓/止损",
                                 had_position=had_position)

            # 第二级：AI 深度分析（预筛通过或关键位命中时）
            if should_analyze:
                    window_start = max(0, len(kline_data) - AI_ANALYSIS_MAX_WINDOW)
                    kline_window = kline_data[window_start:]
                    ctx.last_ai_kline_window = (window_start, len(kline_data) - 1)

                    try:
                        ai_result = await analyzer.analyze_with_window(
                            symbol=ctx.symbol,
                            timeframe=ctx.timeframe,
                            kline_window=kline_window,
                            indicators=indicators,
                            position=ctx.current_position,
                            strategy_rules=ctx.strategy_rules,
                            multi_strategy_rules=ctx.multi_strategy_rules,
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

                        # 深度分析后更新关键位
                        if "key_levels" in ai_result:
                            ctx.key_levels = ai_result["key_levels"]
                        _append_analysis_log(ctx, idx + 1, trigger=ctx.last_trigger_reason or "deep_analysis", analysis=ai_result)
                    except Exception as e:
                        ctx.ai_fail_count += 1
                        logger.warning(f"AI deep analysis failed at kline {idx+1}: {e}")
                        if ctx.ai_fail_count >= 3:
                            ctx.use_ai_real = False
                            logger.warning("AI 连续失败 3 次，降级为规则引擎")

            # 提取 AI 分析摘要（用于 SSE 推送）
            ai_analysis = None
            if ai_result:
                _ma = ai_result.get("market_analysis") or {}
                _tp = ai_result.get("trade_plan") or {}
                ai_analysis = {
                    "trend": _ma.get("trend"),
                    "strength": _ma.get("strength"),
                    "summary": _ma.get("summary"),
                    "decision": ai_result.get("decision"),
                    "confidence": _tp.get("confidence"),
                    "reason": _tp.get("reason"),
                    "source_strategy": ai_result.get("source_strategy", ""),
                }

            # 执行决策
            executor.execute(kline, ai_result, indicators)

            # === 开单检测：上一根无持仓、这一根有持仓了 ===
            if not had_position and ctx.current_position is not None:
                _append_trade_opened_log(ctx, idx + 1)

            # === 平仓检测：上一根有持仓、这一根没了 ===
            if had_position and ctx.current_position is None:
                logger.info(f"Position closed at kline {idx+1}, refreshing key levels")
                window_start = max(0, len(kline_data) - AI_ANALYSIS_MAX_WINDOW)
                kline_window = kline_data[window_start:]
                try:
                    refresh_result = await analyzer.analyze_with_window(
                        symbol=ctx.symbol,
                        timeframe=ctx.timeframe,
                        kline_window=kline_window,
                        indicators=indicators,
                        position=None,
                        strategy_rules=ctx.strategy_rules,
                        multi_strategy_rules=ctx.multi_strategy_rules,
                        account_status={
                            "initial_capital": ctx.initial_capital,
                            "current_equity": ctx.current_equity,
                            "available_cash": ctx.available_cash,
                        },
                        current_kline_index=idx + 1,
                        total_klines=ctx.total_klines,
                    )
                    # 覆盖更新关键位
                    ctx.key_levels = refresh_result.get("key_levels", [])
                    ctx.initial_analysis["trend"] = (refresh_result.get("market_analysis") or {}).get("trend")
                    ctx.initial_analysis["key_levels"] = ctx.key_levels
                    ctx.ai_call_count += 1
                    _append_analysis_log(ctx, idx + 1, trigger="position_closed", analysis=refresh_result)
                except Exception as e:
                    logger.warning(f"Post-close key level refresh failed: {e}")

                # 记录平仓结果日志
                _append_trade_closed_log(ctx, idx + 1)

                # 恢复 AI 分析
                ctx.ai_analysis_paused = False

            # === 持仓免分析恢复检查 ===
            if ctx.current_position is None and ctx.ai_analysis_paused:
                ctx.ai_analysis_paused = False
                logger.info(f"Position closed, resuming AI analysis at kline {idx+1}")

            # 构建当前预筛结果（用于 SSE 实时推送）
            current_precheck = None
            if had_position:
                current_precheck = {
                    "trigger_type": "holding",
                    "passed": False,
                    "reason": "持仓中，跳过预筛",
                }
            elif not ctx.use_ai_real:
                current_precheck = {
                    "trigger_type": "ai_disabled",
                    "passed": False,
                    "reason": "AI已降级为规则引擎，仅处理平仓/止损",
                }
            elif ctx.last_trigger_reason and "key_level_hit" in str(ctx.last_trigger_reason):
                current_precheck = {
                    "trigger_type": "key_level_hit",
                    "passed": True,
                    "reason": f"命中关键位[{ctx.last_trigger_reason.split(':')[-1]}]，跳过预筛直接进入深度分析",
                }
            elif should_analyze and ctx.last_trigger_reason in ("ai_precheck", "local_model"):
                current_precheck = {
                    "trigger_type": ctx.last_trigger_reason,
                    "passed": True,
                    "reason": f"预筛通过（{ctx.last_trigger_reason}），进入深度分析",
                }
            elif not should_analyze and ctx.use_ai_real:
                current_precheck = {
                    "trigger_type": "skipped",
                    "passed": False,
                    "reason": "预筛未通过，跳过AI分析",
                }
            else:
                current_precheck = {
                    "trigger_type": "none",
                    "passed": False,
                    "reason": "无预筛操作",
                }

            # 更新进度（每根 K 线都推，确保实时性）
            progress = 5 + int((idx + 1) / ctx.total_klines * 90)
            current_stage_detail = "suspended"
            if had_position:
                current_stage_detail = "holding"
            elif ctx.current_position is None:
                current_stage_detail = "precheck" if should_analyze else "rule"
            _publish_progress(
                backtest_id, "running", progress,
                idx + 1, ctx.total_klines, ctx.total_trades,
                current_position=ctx.current_position,
                ai_analysis=ai_analysis,
                indicators={
                    "ma5": indicators.get("ma5"),
                    "ma10": indicators.get("ma10"),
                    "rsi_14": indicators.get("rsi_14"),
                    "ema20": indicators.get("ema20"),
                    "ema50": indicators.get("ema50"),
                    "stoch_k": indicators.get("stoch_k"),
                    "stoch_d": indicators.get("stoch_d"),
                    "volume_ma20": indicators.get("volume_ma20"),
                    "close": kline.get("close"),
                },
                message=f"正在推进第 {idx+1}/{ctx.total_klines} 根 K 线",
                # 新增字段
                precheck_total=ctx.precheck_total,
                precheck_triggered=ctx.precheck_triggered,
                ai_call_count=ctx.ai_call_count,
                current_stage_detail=current_stage_detail,
                key_levels=ctx.key_levels,
                initial_analysis=ctx.initial_analysis,
                has_position=ctx.current_position is not None,
                current_equity=ctx.current_equity,
                close_price=kline.get("close"),
                current_precheck=current_precheck,
            )

        # 8. 生成总结
        _publish_progress(backtest_id, "summary", 98, ctx.total_klines, ctx.total_klines,
                          ctx.total_trades, message="正在生成总结报告...")
        summary = _calculate_summary(ctx)

        # 9. 保存交易记录并完成
        await _save_trades_and_finalize(backtest_id, ctx, local_session_maker, "completed", summary)

        # 10. 推送完成事件
        _publish_progress(backtest_id, "done", 100, ctx.total_klines, ctx.total_klines,
                          ctx.total_trades, message="回测完成")

        logger.info(f"AI backtest {backtest_id} completed: {ctx.total_trades} trades, "
                    f"precheck={ctx.precheck_total}/{ctx.precheck_triggered}, "
                    f"ai_calls={ctx.ai_call_count}")
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


async def _save_trades_and_finalize(
    backtest_id: str, ctx: AIBacktestContext,
    session_maker, status: str, summary: Optional[dict] = None,
):
    """保存已完成交易并更新回测状态（抽取为独立方法）。

    用于正常完成和用户终止两种情况。
    """
    async with session_maker() as session:
        from sqlalchemy import select
        backtest = (await session.execute(
            select(AIBacktest).where(AIBacktest.id == backtest_id)
        )).scalar_one()

        # 保存交易明细
        for t in ctx.completed_trades:
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
                # 08-AI回测K线分析优化 新增字段
                ai_window_start=t.get("ai_window_start"),
                ai_window_end=t.get("ai_window_end"),
                trigger_reason=t.get("trigger_reason"),
            )
            session.add(trade)

        # 更新回测记录
        backtest.status = status
        backtest.completed_klines = ctx.current_kline_index
        backtest.completed_at = datetime.now(timezone.utc)

        # 08-AI回测K线分析优化 持久化新增字段
        backtest.ai_call_count = ctx.ai_call_count
        backtest.precheck_total = ctx.precheck_total
        backtest.precheck_triggered = ctx.precheck_triggered
        backtest.initial_analysis = ctx.initial_analysis or None
        backtest.ai_analysis_logs = getattr(ctx, "_analysis_logs", None)

        if status == "completed" and summary:
            backtest.result_summary = summary
        elif status == "cancelled":
            backtest.result_summary = {
                "total_trades": len(ctx.completed_trades),
                "total_pnl": sum(t["pnl"] for t in ctx.completed_trades) if ctx.completed_trades else 0,
                "status": "cancelled",
                "cancelled_at_kline": ctx.current_kline_index,
                "message": "用户终止回测",
            }
        await session.commit()


def _publish_progress(
    backtest_id: str, stage: str, progress: float,
    current_kline: int, total_klines: int, current_trades: int,
    current_position: Optional[dict] = None, message: str = "",
    ai_analysis: Optional[dict] = None,
    indicators: Optional[dict] = None,
    close_price: Optional[float] = None,
    # 08-AI回测K线分析优化 新增参数
    precheck_total: int = 0,
    precheck_triggered: int = 0,
    ai_call_count: int = 0,
    current_stage_detail: str = "",
    key_levels: Optional[List[Dict]] = None,
    initial_analysis: Optional[Dict] = None,
    has_position: bool = False,
    current_equity: Optional[float] = None,
    current_precheck: Optional[Dict] = None,
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
            # 08-AI回测K线分析优化 新增字段
            "precheck_total": precheck_total,
            "precheck_triggered": precheck_triggered,
            "ai_call_count": ai_call_count,
            "current_stage_detail": current_stage_detail,
            "key_levels": key_levels or [],
            "initial_analysis": initial_analysis,
            "has_position": has_position,
            "current_equity": current_equity,
        }
        if ai_analysis is not None:
            payload["ai_analysis"] = ai_analysis
        if indicators is not None:
            payload["indicators"] = indicators
        if close_price is not None:
            payload["close_price"] = close_price
        if current_precheck is not None:
            payload["current_precheck"] = current_precheck

        channel = f"ai-backtest-progress:{backtest_id}"
        r = sync_redis.from_url(settings.REDIS_URL)
        payload_json = json.dumps(payload, ensure_ascii=False)
        r.publish(channel, payload_json)
        # 持久化最后一次进度，供已完成回测的 SSE 端点读取
        r.setex(f"ai-backtest-last-progress:{backtest_id}", 3600, payload_json)
        r.close()
    except Exception as e:
        logger.warning(f"Failed to publish progress: {e}")


def _fetch_klines(symbol: str, timeframe: str, since: datetime, limit: int) -> List[Dict]:
    """获取历史 K 线数据（同步调用 CCXT）。

    Args:
        symbol: 交易对，如 BTC/USDT
        timeframe: 时间周期，如 1h, 15m, 4h, 1d
        since: 起始时间（从此时间开始取数据）
        limit: 获取数量
    """
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


def _timeframe_to_ms(timeframe: str) -> int:
    """将时间周期字符串转换为毫秒数。"""
    unit = timeframe[-1]  # 最后一个字符: m, h, d
    value = int(timeframe[:-1])  # 数字部分
    if unit == "m":
        return value * 60 * 1000
    elif unit == "h":
        return value * 60 * 60 * 1000
    elif unit == "d":
        return value * 24 * 60 * 60 * 1000
    else:
        # 默认按小时处理
        return int(timeframe.rstrip("h")) * 60 * 60 * 1000


def _fetch_backtest_klines(ctx: AIBacktestContext) -> List[Dict]:
    """拉取回测区间全部 K 线（从 start_time 开始）。"""
    return _fetch_klines(ctx.symbol, ctx.timeframe, ctx.start_time, ctx.total_klines)


def _fetch_preheat_klines(ctx: AIBacktestContext) -> List[Dict]:
    """拉取回测开始前的预热 K 线数据。

    预热数据是 start_time 之前的 PREHEAT_COUNT 根 K 线，
    用于计算技术指标和 AI 初始分析。
    """
    # 计算 start_time 之前 PREHEAT_COUNT 根 K 线的时间点
    preheat_offset = PREHEAT_COUNT * _timeframe_to_ms(ctx.timeframe)
    preheat_start = datetime.fromtimestamp(
        (ctx.start_time.timestamp() * 1000 - preheat_offset) / 1000,
        tz=timezone.utc,
    )
    return _fetch_klines(ctx.symbol, ctx.timeframe, preheat_start, PREHEAT_COUNT)


def _calculate_indicators(klines: List[Dict]) -> Dict[str, Any]:
    """计算技术指标（使用 indicators.py 统一计算引擎）。"""
    closes = np.array([k["close"] for k in klines])
    highs = np.array([k["high"] for k in klines])
    lows = np.array([k["low"] for k in klines])
    volumes = np.array([k.get("volume", 0) for k in klines])
    n = len(closes)

    # 转换为 indicators.py 需要的格式: [[ts, o, h, l, c, v], ...]
    ohlcv = [[
        k["timestamp"], k["open"], k["high"], k["low"], k["close"],
        k.get("volume", 0),
    ] for k in klines]

    from app.utils.indicators import calculate_indicators
    all_indicators = calculate_indicators(
        ohlcv,
        indicator_types=["ma", "ema", "rsi", "kdj", "macd", "boll", "atr"],
        params={
            "ema": {"periods": [20, 50]},
            "kdj": {"period": 14},
        },
    )

    indicators: Dict[str, Any] = {}

    # MA（简单移动平均）
    ma_data = all_indicators.get("ma", {})
    for key in ("ma5", "ma10", "ma20"):
        val = ma_data.get(key)
        indicators[key] = float(val) if val is not None else float(closes[-1])

    # EMA（指数移动平均）
    ema_data = all_indicators.get("ema", {})
    for key in ("ema20", "ema50"):
        val = ema_data.get(key)
        indicators[key] = float(val) if val is not None else float(closes[-1])

    # RSI 14
    rsi_data = all_indicators.get("rsi", {})
    rsi_val = rsi_data.get("rsi")
    indicators["rsi_14"] = float(rsi_val) if rsi_val is not None else 50.0

    # Stochastic %K / %D（对应策略中的 Stochastic%D）
    kdj_data = all_indicators.get("kdj", {})
    k_val = kdj_data.get("k")
    d_val = kdj_data.get("d")
    indicators["stoch_k"] = float(k_val) if k_val is not None else 50.0
    indicators["stoch_d"] = float(d_val) if d_val is not None else 50.0

    # 成交量均线（indicators.py 没有 volume 的 MA，保持手动计算）
    indicators["volume_ma20"] = float(np.mean(volumes[-20:])) if n >= 20 else float(np.mean(volumes))

    # 关键水平（手动计算）
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
        # 08-AI回测K线分析优化 新增统计
        "precheck_total": ctx.precheck_total,
        "precheck_triggered": ctx.precheck_triggered,
        "precheck_trigger_rate": round(
            ctx.precheck_triggered / ctx.precheck_total * 100, 2
        ) if ctx.precheck_total > 0 else 0,
        "use_local_model": ctx.use_local_model,
        "initial_trend": ctx.initial_analysis.get("trend", "") if ctx.initial_analysis else "",
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