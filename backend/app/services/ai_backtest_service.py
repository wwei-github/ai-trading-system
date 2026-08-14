"""AI 回测服务层。"""

import json
import logging
import uuid
from datetime import datetime, timedelta
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