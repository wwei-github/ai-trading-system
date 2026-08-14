"""策略服务（Stage 6 完整实现）。

功能：
- 策略 CRUD（含模板策略初始化）
- 策略 DSL 校验
- 回测管理（创建/详情/列表/对比）
- 模拟交易（启动/暂停/恢复/终止/查询）
- 实盘半自动（信号生成/确认下单/风控校验）
"""

import datetime
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ServiceUnavailableException,
)
from app.models.backtest import Backtest
from app.models.backtest_trade import BacktestTrade
from app.models.live_trading import LiveOrder, LiveStrategyInstance
from app.models.paper_trading import PaperAccount, PaperTrade
from app.models.strategy import Strategy
from app.schemas.strategy import (
    BacktestCreate,
    LiveTradeRequest,
    PaperTradeRequest,
    StrategyCreate,
    StrategyUpdate,
)
from app.schemas.strategy_dsl import StrategyDSL
from app.utils.backtest_engine import BacktestResult, compare_backtests
from app.utils.strategy_templates import all_templates


# ---------- 系统用户 ID（用于内置模板策略）
SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


class StrategyService:
    """策略服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- 模板策略初始化 ----------

    async def initialize_templates(self, admin_user_id: uuid.UUID) -> int:
        """初始化内置模板策略（系统启动时调用）。

        将 3 套模板策略写入 DB（若不存在）。
        """
        count = 0
        for tpl in all_templates():
            tpl_id = uuid.UUID(tpl["id"])
            # 检查是否已存在
            result = await self.db.execute(
                select(Strategy).where(Strategy.id == tpl_id)
            )
            existing = result.scalar_one_or_none()
            if existing:
                continue

            strategy = Strategy(
                id=tpl_id,
                user_id=admin_user_id,  # 关联到 Admin 用户
                name=tpl["name"],
                category=tpl["category"],
                description=tpl["description"],
                rules=tpl["rules"],
                params=tpl["params"],
                status="active",
                is_template=True,
            )
            self.db.add(strategy)
            count += 1

        if count > 0:
            await self.db.flush()
            logger.info("已初始化 {} 套内置模板策略", count)
        return count

    # ---------- 策略 CRUD ----------

    async def create_strategy(
        self, user_id: uuid.UUID, data: StrategyCreate
    ) -> Strategy:
        """创建策略（含 DSL 校验）。"""
        # 校验 DSL
        if data.rules:
            try:
                StrategyDSL.model_validate(data.rules)
            except Exception as e:
                raise BadRequestException(
                    message=f"策略规则 DSL 校验失败: {str(e)}",
                    detail={"rules": data.rules},
                )

        strategy = Strategy(
            user_id=user_id,
            name=data.name,
            category=data.category,
            description=data.description,
            rules=data.rules,
            params=data.params,
            source_book_id=data.source_book_id,
            is_template=False,
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
        self, user_id: uuid.UUID, include_templates: bool = True
    ) -> List[Strategy]:
        """获取用户的全部策略（含内置模板）。"""
        from sqlalchemy import or_
        query = select(Strategy).where(
            or_(
                Strategy.user_id == user_id,
                Strategy.is_template == True if include_templates else False,
            )
        ).order_by(Strategy.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_strategy(
        self, strategy_id: uuid.UUID, data: StrategyUpdate
    ) -> Optional[Strategy]:
        """更新策略信息。"""
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            return None

        # 模板策略不可编辑（只读）
        if strategy.is_template:
            raise ForbiddenException(
                message="内置模板策略不可编辑，请克隆后修改"
            )

        update_data = data.model_dump(exclude_unset=True)

        # 校验 DSL
        if "rules" in update_data and update_data["rules"]:
            try:
                StrategyDSL.model_validate(update_data["rules"])
            except Exception as e:
                raise BadRequestException(
                    message=f"策略规则 DSL 校验失败: {str(e)}",
                )

        for key, value in update_data.items():
            setattr(strategy, key, value)
        await self.db.flush()
        return strategy

    async def delete_strategy(
        self, strategy_id: uuid.UUID
    ) -> bool:
        """删除策略（模板策略不可删）。"""
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            return False
        if strategy.is_template:
            raise ForbiddenException(message="内置模板策略不可删除")
        await self.db.delete(strategy)
        await self.db.flush()
        return True

    async def clone_strategy(
        self, strategy_id: uuid.UUID, user_id: uuid.UUID, new_name: Optional[str] = None
    ) -> Strategy:
        """克隆策略（PRD §5.6.1 R2）。"""
        original = await self.get_strategy(strategy_id)
        if original is None:
            raise NotFoundException(message="策略不存在")

        cloned = Strategy(
            user_id=user_id,
            name=new_name or f"{original.name}（副本）",
            category=original.category,
            description=original.description,
            rules=original.rules,
            params=original.params,
            status="draft",
            is_template=False,
        )
        self.db.add(cloned)
        await self.db.flush()
        return cloned

    # ---------- 回测管理 ----------

    async def create_backtest(
        self, user_id: uuid.UUID, data: BacktestCreate
    ) -> Backtest:
        """创建回测记录（触发异步回测任务）。"""
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

        # 触发异步回测任务（Celery 不可用时降级同步执行）
        try:
            from app.tasks.backtest_tasks import run_backtest
            run_backtest.delay(str(backtest.id))
        except Exception as e:
            logger.warning("Celery 不可用，降级同步执行回测 | {}", e)
            try:
                from app.tasks.backtest_tasks import _run_backtest_async
                import asyncio
                asyncio.create_task(_run_backtest_async(str(backtest.id)))
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

    async def get_backtest_trades(
        self, backtest_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[BacktestTrade]:
        """获取回测交易明细。"""
        result = await self.db.execute(
            select(BacktestTrade)
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.entry_time.asc())
            .limit(limit)
            .offset(offset)
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

    async def compare_backtests(
        self, backtest_id_a: uuid.UUID, backtest_id_b: uuid.UUID
    ) -> Dict[str, Any]:
        """对比两次回测结果（PRD §5.6.3 R2）。"""
        bt_a = await self.get_backtest(backtest_id_a)
        bt_b = await self.get_backtest(backtest_id_b)
        if bt_a is None or bt_b is None:
            raise NotFoundException(message="回测记录不存在")
        if bt_a.status != "completed" or bt_b.status != "completed":
            raise BadRequestException(message="仅可对比已完成的回测")

        # 从结果重建 BacktestResult 用于对比
        result_a = self._rebuild_result(bt_a.result)
        result_b = self._rebuild_result(bt_b.result)
        return compare_backtests(result_a, result_b)

    @staticmethod
    def _rebuild_result(result_dict: Dict) -> BacktestResult:
        """从 DB 存储的结果字典重建 BacktestResult（用于对比）。"""
        from app.utils.backtest_engine import BacktestMetrics
        metrics_data = result_dict.get("metrics", {})
        metrics = BacktestMetrics(**{
            k: v for k, v in metrics_data.items()
            if hasattr(BacktestMetrics, k)
        })
        return BacktestResult(
            metrics=metrics,
            equity_curve=result_dict.get("equity_curve", []),
            drawdown_curve=result_dict.get("drawdown_curve", []),
            trades=result_dict.get("trades", []),
            daily_snapshots=result_dict.get("daily_snapshots", []),
            bars=result_dict.get("bars", 0),
        )

    # ---------- 模拟交易 ----------

    async def start_paper_trading(
        self,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID,
        symbol: str,
        timeframe: str = "1h",
        initial_capital: float = 10000.0,
    ) -> PaperAccount:
        """启动模拟交易（PRD §5.6.4 R1）。"""
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            raise NotFoundException(message="策略不存在")

        # 检查是否已有运行中的模拟
        result = await self.db.execute(
            select(PaperAccount).where(
                PaperAccount.user_id == user_id,
                PaperAccount.strategy_id == strategy_id,
                PaperAccount.symbol == symbol,
                PaperAccount.status == "running",
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ConflictException(
                message="该策略+币种已有运行中的模拟交易",
                detail={"paper_account_id": str(existing.id)},
            )

        account = PaperAccount(
            user_id=user_id,
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            initial_capital=Decimal(str(initial_capital)),
            current_equity=Decimal(str(initial_capital)),
            available_cash=Decimal(str(initial_capital)),
            position=0.0,
            status="running",
            strategy_params=strategy.params or {},
            total_trades=0,
            total_pnl=Decimal("0"),
            started_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.db.add(account)
        await self.db.flush()
        return account

    async def list_paper_accounts(
        self, user_id: uuid.UUID, status: Optional[str] = None
    ) -> List[PaperAccount]:
        """获取用户的模拟交易列表。"""
        query = select(PaperAccount).where(PaperAccount.user_id == user_id)
        if status:
            query = query.where(PaperAccount.status == status)
        query = query.order_by(PaperAccount.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_paper_account(
        self, paper_account_id: uuid.UUID
    ) -> Optional[PaperAccount]:
        """获取模拟交易详情。"""
        result = await self.db.execute(
            select(PaperAccount).where(PaperAccount.id == paper_account_id)
        )
        return result.scalar_one_or_none()

    async def control_paper_trading(
        self, paper_account_id: uuid.UUID, action: str
    ) -> PaperAccount:
        """控制模拟交易（暂停/恢复/终止）。

        action: pause / resume / stop
        """
        account = await self.get_paper_account(paper_account_id)
        if account is None:
            raise NotFoundException(message="模拟交易不存在")

        if action == "pause":
            if account.status != "running":
                raise BadRequestException(message="仅运行中可暂停")
            account.status = "paused"
        elif action == "resume":
            if account.status != "paused":
                raise BadRequestException(message="仅暂停状态可恢复")
            account.status = "running"
        elif action == "stop":
            if account.status == "stopped":
                raise BadRequestException(message="已终止")
            account.status = "stopped"
            account.stopped_at = datetime.datetime.now(datetime.timezone.utc)
        else:
            raise BadRequestException(message=f"未知操作: {action}")

        await self.db.flush()
        return account

    async def list_paper_trades(
        self, paper_account_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> List[PaperTrade]:
        """获取模拟交易记录。"""
        result = await self.db.execute(
            select(PaperTrade)
            .where(PaperTrade.paper_account_id == paper_account_id)
            .order_by(PaperTrade.executed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def paper_trade(
        self,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID,
        data: PaperTradeRequest,
    ) -> dict:
        """[兼容] 手动模拟交易（单笔）。"""
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            raise NotFoundException(message="策略不存在")

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

    # ---------- 实盘半自动 ----------

    async def start_live_trading(
        self,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID,
        account_id: uuid.UUID,
        symbol: str,
        timeframe: str = "1h",
        mode: str = "semi_auto",
        risk_params: Optional[Dict] = None,
    ) -> LiveStrategyInstance:
        """启动实盘策略实例（V1 默认半自动）。

        PRD §5.6.5 R6：V1 默认 semi_auto（信号推送后用户确认下单）。
        """
        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            raise NotFoundException(message="策略不存在")

        # 验证账号归属
        from app.services.account_service import AccountService
        account_service = AccountService(self.db)
        account = await account_service.get_account(account_id)
        if account is None:
            raise NotFoundException(message="交易所账号不存在")
        if account.user_id != user_id:
            raise ForbiddenException(message="无权操作此账号")
        if account.status != "active":
            raise BadRequestException(message="账号状态异常，无法启动实盘")

        instance = LiveStrategyInstance(
            user_id=user_id,
            strategy_id=strategy_id,
            account_id=account_id,
            symbol=symbol,
            timeframe=timeframe,
            mode=mode,
            status="running",
            risk_params=risk_control_defaults(risk_params),
            strategy_params=strategy.params or {},
            total_signals=0,
            total_executed=0,
            total_rejected=0,
            total_pnl=Decimal("0"),
            started_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.db.add(instance)
        await self.db.flush()
        return instance

    async def list_live_instances(
        self, user_id: uuid.UUID, status: Optional[str] = None
    ) -> List[LiveStrategyInstance]:
        """获取用户的实盘策略实例列表。"""
        query = select(LiveStrategyInstance).where(
            LiveStrategyInstance.user_id == user_id
        )
        if status:
            query = query.where(LiveStrategyInstance.status == status)
        query = query.order_by(LiveStrategyInstance.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_live_instance(
        self, instance_id: uuid.UUID
    ) -> Optional[LiveStrategyInstance]:
        """获取实盘策略实例详情。"""
        result = await self.db.execute(
            select(LiveStrategyInstance).where(
                LiveStrategyInstance.id == instance_id
            )
        )
        return result.scalar_one_or_none()

    async def pause_live_trading(self, instance_id: uuid.UUID) -> LiveStrategyInstance:
        """暂停实盘策略（仅停止生成新信号，不平仓）。"""
        instance = await self.get_live_instance(instance_id)
        if instance is None:
            raise NotFoundException(message="实盘策略实例不存在")
        if instance.status != "running":
            raise BadRequestException(message="仅运行中可暂停")
        instance.status = "paused"
        await self.db.flush()
        return instance

    async def resume_live_trading(self, instance_id: uuid.UUID) -> LiveStrategyInstance:
        """恢复实盘策略。"""
        instance = await self.get_live_instance(instance_id)
        if instance is None:
            raise NotFoundException(message="实盘策略实例不存在")
        if instance.status != "paused":
            raise BadRequestException(message="仅暂停状态可恢复")
        instance.status = "running"
        await self.db.flush()
        return instance

    async def stop_live_trading(
        self,
        instance_id: uuid.UUID,
        close_positions: bool = False,
        reason: str = "",
    ) -> LiveStrategyInstance:
        """停止实盘策略（PRD §5.6.5 R5）。

        close_positions: True=停止并平所有仓；False=仅停止下单
        """
        result = await self.db.execute(
            select(LiveStrategyInstance).where(
                LiveStrategyInstance.id == instance_id
            )
        )
        instance = result.scalar_one_or_none()
        if instance is None:
            raise NotFoundException(message="实盘策略实例不存在")
        if instance.status == "stopped":
            raise BadRequestException(message="已停止")

        instance.status = "stopped"
        instance.stopped_at = datetime.datetime.now(datetime.timezone.utc)
        instance.stop_reason = reason or ("停止并平仓" if close_positions else "仅停止下单")

        # TODO: close_positions=True 时调用交易所平仓
        await self.db.flush()
        return instance

    async def list_live_orders(
        self,
        user_id: uuid.UUID,
        instance_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[LiveOrder]:
        """获取实盘信号订单列表。"""
        query = select(LiveOrder).where(LiveOrder.user_id == user_id)
        if instance_id:
            query = query.where(LiveOrder.instance_id == instance_id)
        if status:
            query = query.where(LiveOrder.status == status)
        query = query.order_by(LiveOrder.signal_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def confirm_live_order(
        self, order_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict:
        """用户确认实盘信号订单（半自动模式）。

        PRD §5.6.5 R6：信号推送后用户点"确认下单"才执行。
        60s 未确认自动取消。
        """
        result = await self.db.execute(
            select(LiveOrder).where(LiveOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundException(message="信号订单不存在")
        if order.user_id != user_id:
            raise ForbiddenException(message="无权操作此订单")
        if order.status != "pending":
            raise BadRequestException(
                message=f"订单状态非 pending（当前: {order.status}）"
            )

        # 检查是否过期（60s）
        if order.expires_at:
            now = datetime.datetime.now(datetime.timezone.utc)
            if now > order.expires_at:
                order.status = "expired"
                await self.db.flush()
                raise BadRequestException(message="订单已过期（60s 未确认）")

        # 加载实例以获取风控参数
        inst_result = await self.db.execute(
            select(LiveStrategyInstance).where(
                LiveStrategyInstance.id == order.instance_id
            )
        )
        instance = inst_result.scalar_one_or_none()

        # 风控校验（8 阈值）
        risk_passed, risk_reason = await self._check_risk(order, instance)
        order.risk_check_passed = risk_passed
        order.risk_reject_reason = risk_reason
        if not risk_passed:
            order.status = "rejected"
            await self.db.flush()
            raise BadRequestException(
                message=f"风控拦截: {risk_reason}",
                detail={"code": 45001, "reason": risk_reason},
            )

        # 执行下单
        order.status = "confirmed"
        order.confirmed_at = datetime.datetime.now(datetime.timezone.utc)

        from app.services.account_service import AccountService
        account_service = AccountService(self.db)
        account = await account_service.get_account(order.account_id)
        if account is None:
            raise NotFoundException(message="交易所账号不存在")

        client = account_service._build_client(account)
        try:
            exchange_order = await client.create_order(
                symbol=order.symbol,
                order_type=order.order_type,
                side=order.side,
                amount=order.suggested_amount,
                price=order.suggested_price,
            )
            order.status = "executed"
            order.executed_at = datetime.datetime.now(datetime.timezone.utc)
            order.exchange_order_id = str(exchange_order.get("id", ""))
            order.executed_price = float(exchange_order.get("price") or order.suggested_price or 0)
            order.executed_amount = float(exchange_order.get("amount") or order.suggested_amount)
            await self.db.flush()

            # 更新实例统计
            inst_result = await self.db.execute(
                select(LiveStrategyInstance).where(
                    LiveStrategyInstance.id == order.instance_id
                )
            )
            instance = inst_result.scalar_one_or_none()
            if instance:
                instance.total_executed += 1
                await self.db.flush()

            return {
                "order_id": str(order.id),
                "status": "executed",
                "exchange_order_id": order.exchange_order_id,
                "executed_price": order.executed_price,
                "executed_amount": order.executed_amount,
            }
        except Exception as e:
            order.status = "rejected"
            order.risk_reject_reason = f"下单失败: {str(e)}"
            await self.db.flush()
            raise BadRequestException(message=f"实盘下单失败: {str(e)}")
        finally:
            await client.close()

    async def live_trade(
        self,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID,
        data: LiveTradeRequest,
    ) -> dict:
        """[兼容] 直接实盘下单（需二次确认）。"""
        if not data.confirm:
            raise BadRequestException(
                message="实盘交易需二次确认",
                detail={"confirm": "必须将 confirm 设置为 true"},
            )

        strategy = await self.get_strategy(strategy_id)
        if strategy is None:
            raise NotFoundException(message="策略不存在")

        from app.services.account_service import AccountService
        account_service = AccountService(self.db)
        account = await account_service.get_account(data.account_id)
        if account is None:
            raise NotFoundException(message="账号不存在")
        if account.status != "active":
            raise BadRequestException(message="账号状态异常，无法下单")

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
            )
        finally:
            await client.close()

    # ---------- 风控校验（8 阈值，委托 RiskController） ----------

    async def _check_risk(
        self, order: LiveOrder, instance: Optional[LiveStrategyInstance] = None
    ) -> tuple:
        """实盘下单前风控校验（8 阈值，对齐 PRD §9.2）。

        委托给 RiskController（Stage 9.1），违规时自动写审计日志 + 发邮件。
        """
        from app.services.risk_service import RiskController

        controller = RiskController(self.db)
        return await controller.check_order(order, instance)

    async def reject_live_order(
        self, order_id: uuid.UUID, user_id: uuid.UUID, reason: str = ""
    ) -> LiveOrder:
        """用户拒绝实盘信号订单（半自动模式）。"""
        result = await self.db.execute(
            select(LiveOrder).where(LiveOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise NotFoundException(message="信号订单不存在")
        if order.user_id != user_id:
            raise ForbiddenException(message="无权操作此订单")
        if order.status != "pending":
            raise BadRequestException(
                message=f"订单状态非 pending（当前: {order.status}）"
            )

        order.status = "rejected"
        order.risk_check_passed = False
        order.risk_reject_reason = reason or "用户手动拒绝"

        # 更新实例统计
        inst_result = await self.db.execute(
            select(LiveStrategyInstance).where(
                LiveStrategyInstance.id == order.instance_id
            )
        )
        instance = inst_result.scalar_one_or_none()
        if instance:
            instance.total_rejected += 1

        await self.db.flush()
        return order


# 风控参数默认值（从 risk_service 导入，保持向后兼容）
from app.services.risk_service import risk_control_defaults  # noqa: E402
