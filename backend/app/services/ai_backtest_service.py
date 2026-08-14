"""AI 回测服务层。"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models.ai_backtest import AIBacktest
from app.models.ai_backtest_trade import AIBacktestTrade
from app.models.strategy import Strategy
from app.schemas.ai_backtest import (
    AIBacktestCreate,
    AIBacktestListResponse,
    AIBacktestProgress,
    AIBacktestResponse,
    AIBacktestTradeResponse,
)
from app.services.coin_service import CoinService
from app.services.provider_factory import ProviderFactory
from app.tasks.ai_backtest_tasks import run_ai_backtest

logger = logging.getLogger(__name__)


class AIBacktestService:
    """AI 回测业务编排。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.coin_service = CoinService(db)

    async def create_backtest(
        self, user_id: uuid.UUID, data: AIBacktestCreate
    ) -> AIBacktestResponse:
        """创建并启动 AI 回测。"""

        # 1. 并发控制：同一用户最多 3 个正在运行的回测
        await self._check_concurrency_limit(user_id)

        # 2. 验证策略存在且有效
        strategy = await self._validate_strategy(data.strategy_id, user_id)

        # 3. 计算总 K 线数
        total_klines = await self._calculate_total_klines(
            data.symbol, data.timeframe, data.start_time,
            data.mode, data.kline_count, data.time_span_value, data.time_span_unit,
        )

        # 4. 验证预热数据可用
        await self._validate_preheat_data(data.symbol, data.timeframe, data.start_time)

        # 5. 创建回测记录
        backtest = AIBacktest(
            strategy_id=data.strategy_id,
            user_id=user_id,
            symbol=data.symbol,
            timeframe=data.timeframe,
            start_time=data.start_time,
            mode=data.mode,
            kline_count=data.kline_count if data.mode == "kline_count" else None,
            time_span_value=data.time_span_value if data.mode == "time_span" else None,
            time_span_unit=data.time_span_unit if data.mode == "time_span" else None,
            initial_capital=data.initial_capital,
            fee_rate=data.fee_rate,
            use_ai=data.use_ai,
            total_klines=total_klines,
            status="pending",
        )
        self.db.add(backtest)
        await self.db.flush()

        # 6. 异步提交 Celery 任务
        task = run_ai_backtest.delay(str(backtest.id))
        logger.info(f"AI backtest {backtest.id} submitted, task_id={task.id}")

        # 7. 返回响应
        return await self._build_response(backtest)

    async def _check_concurrency_limit(self, user_id: uuid.UUID) -> None:
        """检查并发限制：同一用户最多 3 个正在运行的回测。"""
        result = await self.db.execute(
            select(func.count(AIBacktest.id))
            .where(
                AIBacktest.user_id == user_id,
                AIBacktest.status == "running",
            )
        )
        running_count = result.scalar_one()
        if running_count >= 3:
            raise BadRequestException(message="同一用户最多同时运行 3 个 AI 回测")

    async def _validate_strategy(
        self, strategy_id: uuid.UUID, user_id: uuid.UUID
    ) -> Strategy:
        """验证策略有效。"""
        result = await self.db.execute(
            select(Strategy).where(
                Strategy.id == strategy_id,
                Strategy.user_id == user_id,
            )
        )
        strategy = result.scalar_one_or_none()
        if strategy is None:
            raise NotFoundException(message="策略不存在")
        if not strategy.rules:
            raise BadRequestException(message="策略规则为空")
        return strategy

    async def _calculate_total_klines(
        self, symbol: str, timeframe: str, start_time: datetime,
        mode: str, kline_count: Optional[int],
        time_span_value: Optional[int], time_span_unit: Optional[str],
    ) -> int:
        """计算回测总 K 线数。"""
        if mode == "kline_count":
            return kline_count or 100
        elif mode == "time_span":
            # 时间跨度转小时
            hours = (time_span_value or 7) * (
                24 if time_span_unit == "day" else 1
            )
            # 根据周期计算 K 线数
            timeframe_hours = {"15m": 0.25, "1h": 1, "4h": 4, "1d": 24}
            per_kline_hours = timeframe_hours.get(timeframe, 1)
            return max(1, int(hours / per_kline_hours))
        return 100

    async def _validate_preheat_data(
        self, symbol: str, timeframe: str, start_time: datetime
    ) -> None:
        """验证预热数据可用。"""
        try:
            klines = await self.coin_service.get_kline_data(
                symbol=symbol, timeframe=timeframe,
                limit=1,
            )
            if not klines:
                raise BadRequestException(
                    message="无法获取历史 K 线数据，请检查交易对是否正确"
                )
        except Exception as e:
            raise BadRequestException(
                message=f"数据源不可用: {str(e)}"
            )

    async def get_backtest(
        self, backtest_id: uuid.UUID, user_id: uuid.UUID
    ) -> AIBacktestResponse:
        """获取回测详情。"""
        backtest = await self._verify_ownership(backtest_id, user_id)
        return await self._build_response(backtest)

    async def get_trades(
        self, backtest_id: uuid.UUID, user_id: uuid.UUID,
        page: int = 1, page_size: int = 20,
    ) -> Tuple[List[AIBacktestTradeResponse], int]:
        """获取交易明细（分页）。"""
        await self._verify_ownership(backtest_id, user_id)

        count_result = await self.db.execute(
            select(func.count(AIBacktestTrade.id))
            .where(AIBacktestTrade.backtest_id == backtest_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(AIBacktestTrade)
            .where(AIBacktestTrade.backtest_id == backtest_id)
            .order_by(AIBacktestTrade.index.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        trades = list(result.scalars().all())
        return (
            [AIBacktestTradeResponse.model_validate(t) for t in trades],
            total,
        )

    async def list_history(
        self, user_id: uuid.UUID, page: int = 1, page_size: int = 10,
    ) -> Tuple[List[AIBacktestListResponse], int]:
        """获取用户历史回测列表。"""
        count_result = await self.db.execute(
            select(func.count(AIBacktest.id))
            .where(AIBacktest.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(AIBacktest)
            .where(AIBacktest.user_id == user_id)
            .order_by(AIBacktest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        backtests = list(result.scalars().all())

        items = []
        for bt in backtests:
            trade_count = 0
            total_pnl = None
            win_rate = None
            if bt.result_summary:
                trade_count = bt.result_summary.get("total_trades", 0)
                total_pnl = bt.result_summary.get("total_pnl")
                win_rate = bt.result_summary.get("win_rate")
            items.append(
                AIBacktestListResponse(
                    id=bt.id,
                    strategy_name=bt.strategy.name if bt.strategy else "未知",
                    symbol=bt.symbol,
                    timeframe=bt.timeframe,
                    status=bt.status,
                    total_klines=bt.total_klines,
                    completed_klines=bt.completed_klines,
                    initial_capital=float(bt.initial_capital),
                    total_pnl=float(total_pnl) if total_pnl is not None else None,
                    win_rate=win_rate,
                    trade_count=trade_count,
                    created_at=bt.created_at,
                    completed_at=bt.completed_at,
                )
            )
        return items, total

    async def cancel_backtest(
        self, backtest_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """取消回测（仅 pending 状态）。"""
        backtest = await self._verify_ownership(backtest_id, user_id)
        if backtest.status != "pending":
            raise BadRequestException(message="只能取消待开始状态的回测")
        await self.db.delete(backtest)

    async def stop_backtest(
        self, backtest_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """终止运行中的回测。

        1. 设置 Redis 停止标志 (TTL 3600s)
        2. 更新 DB 状态为 cancelling (running) 或 cancelled (pending)
        """
        backtest = await self._verify_ownership(backtest_id, user_id)
        if backtest.status not in ("running", "pending"):
            raise BadRequestException(message="只能终止运行中或待开始的回测")

        # 1. 设置 Redis 停止标志
        try:
            import redis as sync_redis
            r = sync_redis.from_url(settings.REDIS_URL)
            stop_key = f"stop:ai-backtest:{backtest_id}"
            r.setex(stop_key, 3600, "1")
            r.close()
        except Exception as e:
            logger.warning(f"Failed to set Redis stop flag: {e}")

        # 2. 更新 DB 状态
        if backtest.status == "running":
            backtest.status = "cancelling"
        else:
            backtest.status = "cancelled"
            backtest.completed_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def analyze_results(
        self, backtest_id: uuid.UUID, user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """AI 分析回测结果。"""
        backtest = await self._verify_ownership(backtest_id, user_id)
        if backtest.status != "completed":
            raise BadRequestException(message="只有已完成回测可以分析")

        # 读取交易明细
        result = await self.db.execute(
            select(AIBacktestTrade)
            .where(AIBacktestTrade.backtest_id == backtest_id)
            .order_by(AIBacktestTrade.index.asc())
        )
        trades = list(result.scalars().all())

        # 构建分析 Prompt
        prompt = self._build_analysis_prompt(backtest, trades)

        # 调用 LLM
        provider = await ProviderFactory.get_active_provider(self.db)
        raw_result = await provider.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        analysis = self._parse_analysis_result(raw_result)

        # 保存到 result_summary
        summary = backtest.result_summary or {}
        summary["ai_analysis"] = analysis
        backtest.result_summary = summary
        await self.db.flush()

        return analysis

    async def optimize_strategy(
        self, backtest_id: uuid.UUID, user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """基于回测结果生成新的优化策略。"""
        backtest = await self._verify_ownership(backtest_id, user_id)
        if backtest.status != "completed":
            raise BadRequestException(message="只有已完成回测可以优化")

        # 读取原策略
        strategy_result = await self.db.execute(
            select(Strategy).where(Strategy.id == backtest.strategy_id)
        )
        original_strategy = strategy_result.scalar_one_or_none()
        if not original_strategy:
            raise NotFoundException(message="原策略不存在")

        # 读取 AI 分析结果
        analysis = (backtest.result_summary or {}).get("ai_analysis", {})
        if not analysis:
            raise BadRequestException(message="请先进行 AI 分析")

        # 构建优化 Prompt
        prompt = self._build_optimize_prompt(original_strategy, backtest, analysis)

        # 调用 LLM
        provider = await ProviderFactory.get_active_provider(self.db)
        raw_result = await provider.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        new_rules = self._parse_optimize_result(raw_result)

        # 计算版本号
        version = self._get_next_version(original_strategy.name, user_id)

        # 创建新策略
        new_strategy = Strategy(
            user_id=user_id,
            name=f"{original_strategy.name} - 优化版 v{version}",
            category=original_strategy.category,
            rules=new_rules,
            description=f"AI 基于回测 {backtest_id} 自动优化生成",
            extra={
                "source_backtest_id": str(backtest_id),
                "original_strategy_id": str(original_strategy.id),
                "optimized_by_ai": True,
            },
        )
        self.db.add(new_strategy)
        await self.db.flush()

        return {"id": new_strategy.id, "name": new_strategy.name, "rules": new_rules}

    # ---------- Prompt 构建与解析（私有方法） ----------

    def _build_analysis_prompt(self, backtest: AIBacktest, trades: List[AIBacktestTrade]) -> str:
        """构建回测结果分析 Prompt。"""
        summary = backtest.result_summary or {}
        # 交易明细摘要
        trade_summary = []
        for t in trades[:50]:  # 最多取前 50 条
            direction = "多" if t.direction == "long" else "空"
            pnl = float(t.pnl) if t.pnl else 0
            trade_summary.append(
                f"  #{t.index} {direction} 开{float(t.entry_price):.2f} "
                f"平{float(t.exit_price) if t.exit_price else '-':.2f} "
                f"盈亏{pnl:+.2f} 理由:{t.open_reason or '-'}"
            )
        trade_summary_str = "\n".join(trade_summary[:50]) or "  无交易记录"

        strategy_rules = backtest.strategy.rules if backtest.strategy else {}
        strategy_name = backtest.strategy.name if backtest.strategy else "未知"

        return f"""你是一个专业的量化交易策略分析专家。请对以下回测结果进行深入分析。

## 回测基本信息
- 策略名称: {strategy_name}
- 策略类型: {backtest.strategy.category if backtest.strategy else "未知"}
- 交易对: {backtest.symbol}
- 时间周期: {backtest.timeframe}
- 回测K线数: {backtest.total_klines}
- 初始资金: {float(backtest.initial_capital)} USDT

## 回测结果摘要
{json.dumps(summary, ensure_ascii=False, indent=2)}

## 交易明细摘要
{trade_summary_str}

## 策略规则
{json.dumps(strategy_rules, ensure_ascii=False, indent=2)}

请分析以上回测结果，输出 JSON 格式：
{{
  "overall_assessment": "整体表现评估（2-3句话）",
  "strengths": ["优势1", "优势2"],
  "weaknesses": ["不足1", "不足2"],
  "market_adaptability": {{
    "trend_market": "优秀/良好/一般/较差",
    "range_market": "优秀/良好/一般/较差",
    "volatile_market": "优秀/良好/一般/较差"
  }},
  "improvement_suggestions": ["建议1", "建议2", "建议3"],
  "score": 75
}}

注意：
- score 范围 0-100，基于胜率、盈亏比、最大回撤、夏普比率等综合评估
- improvement_suggestions 必须具体可行，不少于3条
- 只输出 JSON，不要输出其他文字"""

    def _build_optimize_prompt(
        self, original_strategy: Strategy, backtest: AIBacktest, analysis: Dict[str, Any]
    ) -> str:
        """构建策略优化 Prompt。"""
        summary = backtest.result_summary or {}

        return f"""你是一个专业的量化交易策略优化专家。请基于以下回测结果和AI分析，优化策略规则。

## 原策略信息
- 策略名称: {original_strategy.name}
- 策略类型: {original_strategy.category}

## 原策略规则
{json.dumps(original_strategy.rules, ensure_ascii=False, indent=2) if original_strategy.rules else "无"}

## 回测结果
{json.dumps(summary, ensure_ascii=False, indent=2)}

## AI 分析结果
{json.dumps(analysis, ensure_ascii=False, indent=2)}

请基于以上信息，生成优化后的策略规则。输出 JSON 格式如下：
{{
  "category": "{original_strategy.category}",
  "entry_rules": [
    {{"condition": "入场条件1", "params": {{}}}},
    {{"condition": "入场条件2", "params": {{}}}}
  ],
  "exit_rules": [
    {{"condition": "出场条件1", "params": {{}}}}
  ],
  "position_sizing": {{
    "method": "fixed_percent",
    "base_percent": 30
  }},
  "risk_control": {{
    "max_drawdown_pct": 15,
    "max_position_risk_pct": 2
  }},
  "prerequisites": {{
    "single_position": {{"enabled": true, "description": "单仓规则"}},
    "mandatory_stop_loss": {{"enabled": true, "default_stop_loss_pct": 3}},
    "strict_execution": {{"enabled": true, "description": "严格执规"}}
  }},
  "optimization_notes": "优化说明（2-3句话）"
}}

注意：
- 保留原策略的核心逻辑，只优化参数和条件
- 必须包含三条默认前提规则
- 只输出 JSON，不要输出其他文字"""

    def _parse_analysis_result(self, raw: str) -> Dict[str, Any]:
        """解析 AI 分析结果 JSON。"""
        import re
        # 尝试提取 JSON 块
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            raise BadRequestException(message="AI 分析结果格式异常，无法解析")
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            raise BadRequestException(message="AI 分析结果 JSON 解析失败")

    def _parse_optimize_result(self, raw: str) -> Dict[str, Any]:
        """解析策略优化结果 JSON。"""
        return self._parse_analysis_result(raw)

    def _get_next_version(self, strategy_name: str, user_id: uuid.UUID) -> int:
        """计算下一个优化版本号（暂返回 1）。"""
        return 1

    async def _verify_ownership(
        self, backtest_id: uuid.UUID, user_id: uuid.UUID
    ) -> AIBacktest:
        """验证回测所有权。"""
        result = await self.db.execute(
            select(AIBacktest).where(
                AIBacktest.id == backtest_id,
                AIBacktest.user_id == user_id,
            )
        )
        backtest = result.scalar_one_or_none()
        if backtest is None:
            raise NotFoundException(message="回测记录不存在")
        return backtest

    async def _build_response(
        self, backtest: AIBacktest
    ) -> AIBacktestResponse:
        """构建响应对象。"""
        progress = 0.0
        if backtest.total_klines > 0 and backtest.completed_klines > 0:
            progress = round(
                (backtest.completed_klines / backtest.total_klines) * 100, 1
            )

        return AIBacktestResponse(
            id=backtest.id,
            strategy_id=backtest.strategy_id,
            strategy_name=backtest.strategy.name if backtest.strategy else "",
            symbol=backtest.symbol,
            timeframe=backtest.timeframe,
            start_time=backtest.start_time,
            end_time=backtest.end_time,
            mode=backtest.mode,
            kline_count=backtest.kline_count,
            time_span_value=backtest.time_span_value,
            time_span_unit=backtest.time_span_unit,
            initial_capital=float(backtest.initial_capital),
            fee_rate=backtest.fee_rate,
            use_ai=backtest.use_ai,
            status=backtest.status,
            total_klines=backtest.total_klines,
            completed_klines=backtest.completed_klines,
            progress=progress,
            started_at=backtest.started_at,
            completed_at=backtest.completed_at,
            result_summary=backtest.result_summary,
            created_at=backtest.created_at,
        )