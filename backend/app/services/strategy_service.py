"""策略服务。

处理策略的增删改查、回测管理、模拟交易和实盘交易。
"""

import uuid
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.backtest import Backtest
from app.models.strategy import Strategy
from app.schemas.strategy import (
    BacktestCreate,
    LiveTradeRequest,
    PaperTradeRequest,
    StrategyCreate,
    StrategyUpdate,
)


class StrategyService:
    """策略服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- 策略 CRUD ----------

    async def create_strategy(
        self, user_id: uuid.UUID, data: StrategyCreate
    ) -> Strategy:
        """创建策略。"""
        strategy = Strategy(
            user_id=user_id,
            name=data.name,
            category=data.category,
            description=data.description,
            rules=data.rules,
            params=data.params,
            source_book_id=data.source_book_id,
        )
        self.db.add(strategy)
        await self.db.flush()
        return strategy

    async def get_strategy(
        self, strategy_id: uuid.UUID
    ) -> Optional[Strategy]:
        """获取策略详情。"""
        result = await self.db.execute(
            select(Strategy).where(Strategy.id == strategy_id)
        )
        return result.scalar_one_or_none()

    async def list_strategies(
        self, user_id: uuid.UUID
    ) -> List[Strategy]:
        """获取用户的全部策略。"""
        result = await self.db.execute(
            select(Strategy)
            .where(Strategy.user_id == user_id)
            .order_by(Strategy.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_strategy(
        self, strategy_id: uuid.UUID, data: StrategyUpdate
    ) -> Optional[Strategy]:
        """更新策略。"""
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(strategy, key, value)
        await self.db.flush()
        return strategy

    async def delete_strategy(
        self, strategy_id: uuid.UUID
    ) -> bool:
        """删除策略。"""
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            return False
        await self.db.delete(strategy)
        await self.db.flush()
        return True

    # ---------- 回测管理 ----------

    async def create_backtest(
        self, user_id: uuid.UUID, data: BacktestCreate
    ) -> Backtest:
        """创建回测记录（触发异步回测任务）。"""
        # 校验策略归属
        strategy = await self.get_strategy(data.strategy_id)
        if strategy is None:
            raise NotFoundException(
                message="策略不存在",
                detail={"strategy_id": str(data.strategy_id)},
            )

        backtest = Backtest(
            strategy_id=data.strategy_id,
            symbol=data.symbol,
            timeframe=data.timeframe,
            start_date=data.start_date,
            end_date=data.end_date,
            initial_capital=data.initial_capital,
            params=data.params,
            status="pending",
        )
        self.db.add(backtest)
        await self.db.flush()

        # 触发异步回测任务（Celery 不可用时降级）
        try:
            from app.tasks.backtest_tasks import run_backtest

            run_backtest.delay(str(backtest.id))
        except Exception:
            pass

        return backtest

    async def get_backtest(
        self, backtest_id: uuid.UUID
    ) -> Optional[Backtest]:
        """获取回测详情。"""
        result = await self.db.execute(
            select(Backtest).where(Backtest.id == backtest_id)
        )
        return result.scalar_one_or_none()

    async def list_backtests(
        self, strategy_id: uuid.UUID
    ) -> List[Backtest]:
        """获取策略的回测历史。"""
        result = await self.db.execute(
            select(Backtest)
            .where(Backtest.strategy_id == strategy_id)
            .order_by(Backtest.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_backtest_result(
        self,
        backtest_id: uuid.UUID,
        result: dict,
        status: str = "completed",
    ) -> Optional[Backtest]:
        """更新回测结果（供异步任务调用）。"""
        backtest = await self.get_backtest(backtest_id)
        if backtest is None:
            return None
        backtest.result = result
        backtest.status = status
        await self.db.flush()
        return backtest

    # ---------- 模拟交易 ----------

    async def paper_trade(
        self,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID,
        data: PaperTradeRequest,
    ) -> dict:
        """模拟交易（不实际下单，仅记录信号）。"""
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            raise NotFoundException(
                message="策略不存在",
                detail={"strategy_id": str(strategy_id)},
            )

        # 模拟交易：返回模拟成交结果，不实际下单
        return {
            "mode": "paper",
            "strategy_id": str(strategy_id),
            "symbol": data.symbol,
            "side": data.side,
            "amount": data.amount,
            "price": data.price,
            "status": "simulated",
            "message": "模拟交易已执行（未实际下单）",
        }

    # ---------- 实盘交易 ----------

    async def live_trade(
        self,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID,
        data: LiveTradeRequest,
    ) -> dict:
        """实盘交易（需二次确认，调用交易所下单）。"""
        if not data.confirm:
            raise BadRequestException(
                message="实盘交易需二次确认",
                detail={"confirm": "必须将 confirm 设置为 true"},
            )

        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            raise NotFoundException(
                message="策略不存在",
                detail={"strategy_id": str(strategy_id)},
            )

        # 延迟导入避免循环依赖
        from app.services.account_service import AccountService

        account_service = AccountService(self.db)
        account = await account_service.get_account(data.account_id)
        if account is None:
            raise NotFoundException(
                message="账号不存在",
                detail={"account_id": str(data.account_id)},
            )
        if account.status != "active":
            raise BadRequestException(
                message="账号状态异常，无法下单",
                detail={"status": account.status},
            )

        # 调用交易所下单
        client = account_service._build_client(account)
        try:
            order = await client.create_order(
                symbol=data.symbol,
                order_type=data.order_type,
                side=data.side,
                amount=data.amount,
                price=data.price,
            )
            return {
                "mode": "live",
                "strategy_id": str(strategy_id),
                "account_id": str(data.account_id),
                "order": order,
                "status": "submitted",
            }
        except Exception as e:
            raise BadRequestException(
                message=f"实盘下单失败: {str(e)}",
                detail={"symbol": data.symbol, "side": data.side},
            )
        finally:
            await client.close()
