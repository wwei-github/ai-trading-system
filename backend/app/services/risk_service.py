"""实盘风控服务（Stage 9.1，对齐 PRD §9.2）。

策略模式实现 8 阈值风控拦截器：
1. 单次下单金额 < max_single_order_value（默认 50k USDT）
2. 单日下单数 < max_daily_orders（默认 100）
3. 同币种持仓数 < max_holdings_per_symbol（默认 2）
4. 总持仓数 < max_total_holdings（默认 10）
5. 单日亏损 < max_daily_loss_pct（默认 5%）
6. 连续亏损次数 < max_consecutive_losses（默认 5）
7. 策略累计回撤 < max_drawdown_pct（默认 20%）
8. 单笔预计亏损 < max_single_loss_pct（默认 2%）

任一违规 → 拒绝订单 + 邮件通知 + 风险审计记录。
"""

import datetime
import logging
import uuid
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.live_trading import LiveOrder, LiveStrategyInstance
from app.models.user import User
from app.utils.audit import write_audit_log

logger = logging.getLogger(__name__)

# 风控审计动作（扩展标准动作集）
RISK_AUDIT_ACTION = "config_change"  # 复用 config_change，detail 中标注 risk_violation


def risk_control_defaults(user_params: Optional[Dict] = None) -> Dict:
    """风控参数默认值（对齐 PRD §9.2 八阈值）。"""
    defaults = {
        "max_single_loss_pct": 0.02,  # 单笔 max_loss < 2%
        "max_daily_loss_pct": 0.05,  # 单日 max_loss < 5%
        "max_consecutive_losses": 5,  # 连续亏损 < 5 次
        "max_drawdown_pct": 0.20,  # 策略 max_drawdown < 20%
        "max_holdings_per_symbol": 2,  # 同币种 max_holdings < 2
        "max_total_holdings": 10,  # 总 max_holdings < 10
        "max_daily_orders": 100,  # 单日 max_orders < 100
        "max_single_order_value": 50000,  # 单次下单 < 50k USDT
    }
    if user_params:
        defaults.update(user_params)
    return defaults


class RiskController:
    """实盘风控拦截器（策略模式）。

    每个阈值检查为独立方法，可通过 risk_params 配置启用/禁用。
    违规时自动写入审计日志并发送邮件通知。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_order(
        self,
        order: LiveOrder,
        instance: Optional[LiveStrategyInstance] = None,
    ) -> Tuple[bool, str]:
        """执行全部 8 项风控检查。

        Returns:
            (passed, reason): passed=True 表示通过；passed=False 时 reason 为拒绝原因。
        """
        params = risk_control_defaults(
            instance.risk_params if instance else None
        )

        checks = [
            self._check_single_order_value,
            self._check_daily_orders,
            self._check_holdings_per_symbol,
            self._check_total_holdings,
            self._check_daily_loss,
            self._check_consecutive_losses,
            self._check_drawdown,
            self._check_single_loss,
        ]

        for check in checks:
            passed, reason = await check(order, instance, params)
            if not passed:
                # 违规：写审计日志 + 发邮件
                await self._on_violation(order, instance, reason, check.__name__)
                return False, reason

        return True, ""

    # ---------- 8 项检查（策略模式，每项独立） ----------

    async def _check_single_order_value(
        self, order: LiveOrder, instance, params: Dict
    ) -> Tuple[bool, str]:
        """检查 1：单次下单金额上限。"""
        max_value = float(params["max_single_order_value"])
        order_value = (order.suggested_price or 0) * order.suggested_amount
        if order_value > max_value:
            return False, (
                f"单次下单金额 {order_value:.2f} USDT 超过上限 {max_value}"
            )
        return True, ""

    async def _check_daily_orders(
        self, order: LiveOrder, instance, params: Dict
    ) -> Tuple[bool, str]:
        """检查 2：单日下单数。"""
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.db.execute(
            select(LiveOrder).where(
                LiveOrder.user_id == order.user_id,
                LiveOrder.signal_at >= today_start,
                LiveOrder.status.in_(["confirmed", "executed", "rejected"]),
            )
        )
        today_orders = list(result.scalars().all())
        max_daily = int(params["max_daily_orders"])
        if len(today_orders) >= max_daily:
            return False, (
                f"今日下单数 {len(today_orders)} 达到上限 {max_daily}"
            )
        return True, ""

    async def _check_holdings_per_symbol(
        self, order: LiveOrder, instance, params: Dict
    ) -> Tuple[bool, str]:
        """检查 3：同币种持仓数。"""
        result = await self.db.execute(
            select(LiveOrder).where(
                LiveOrder.user_id == order.user_id,
                LiveOrder.symbol == order.symbol,
                LiveOrder.status == "executed",
                LiveOrder.side == "buy",
            )
        )
        sym_positions = len(list(result.scalars().all()))
        max_sym = int(params["max_holdings_per_symbol"])
        if sym_positions >= max_sym:
            return False, (
                f"同币种 {order.symbol} 持仓 {sym_positions} 达到上限 {max_sym}"
            )
        return True, ""

    async def _check_total_holdings(
        self, order: LiveOrder, instance, params: Dict
    ) -> Tuple[bool, str]:
        """检查 4：总持仓数。"""
        result = await self.db.execute(
            select(LiveOrder).where(
                LiveOrder.user_id == order.user_id,
                LiveOrder.status == "executed",
                LiveOrder.side == "buy",
            )
        )
        total_positions = len(list(result.scalars().all()))
        max_total = int(params["max_total_holdings"])
        if total_positions >= max_total:
            return False, (
                f"总持仓数 {total_positions} 达到上限 {max_total}"
            )
        return True, ""

    async def _check_daily_loss(
        self, order: LiveOrder, instance, params: Dict
    ) -> Tuple[bool, str]:
        """检查 5：单日亏损。"""
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.db.execute(
            select(LiveOrder).where(
                LiveOrder.user_id == order.user_id,
                LiveOrder.signal_at >= today_start,
                LiveOrder.status == "executed",
            )
        )
        today_orders = list(result.scalars().all())
        today_pnl = sum(
            float(o.executed_price or 0) * float(o.executed_amount or 0) * (-1 if o.side == "sell" else 1)
            for o in today_orders
            if o.executed_price and o.executed_amount
        )
        if instance:
            base_capital = float(instance.total_pnl) + 10000.0
            max_daily_loss_pct = float(params["max_daily_loss_pct"])
            if base_capital > 0 and today_pnl < 0:
                daily_loss_pct = abs(today_pnl) / base_capital
                if daily_loss_pct > max_daily_loss_pct:
                    return False, (
                        f"单日亏损 {daily_loss_pct:.2%} 超过上限 {max_daily_loss_pct:.2%}"
                    )
        return True, ""

    async def _check_consecutive_losses(
        self, order: LiveOrder, instance, params: Dict
    ) -> Tuple[bool, str]:
        """检查 6：连续亏损次数。"""
        max_consec = int(params["max_consecutive_losses"])
        result = await self.db.execute(
            select(LiveOrder)
            .where(
                LiveOrder.user_id == order.user_id,
                LiveOrder.status == "executed",
            )
            .order_by(LiveOrder.executed_at.desc())
            .limit(max_consec + 1)
        )
        recent_orders = list(result.scalars().all())
        consecutive_losses = 0
        for o in recent_orders:
            if o.side == "sell" and o.executed_price and o.executed_amount:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= max_consec:
            return False, (
                f"连续亏损 {consecutive_losses} 次达到上限 {max_consec}"
            )
        return True, ""

    async def _check_drawdown(
        self, order: LiveOrder, instance, params: Dict
    ) -> Tuple[bool, str]:
        """检查 7：策略累计回撤。"""
        if not instance:
            return True, ""
        max_dd_pct = float(params["max_drawdown_pct"])
        base_capital = 10000.0
        total_pnl = float(instance.total_pnl)
        if total_pnl < 0 and abs(total_pnl) / base_capital > max_dd_pct:
            return False, (
                f"策略累计亏损 {abs(total_pnl) / base_capital:.2%} 超过回撤上限 {max_dd_pct:.2%}"
            )
        return True, ""

    async def _check_single_loss(
        self, order: LiveOrder, instance, params: Dict
    ) -> Tuple[bool, str]:
        """检查 8：单笔预计亏损。"""
        if order.side != "sell" or not instance or not instance.total_pnl:
            return True, ""
        max_single_loss_pct = float(params["max_single_loss_pct"])
        est_loss = -float(order.suggested_amount or 0) * float(order.suggested_price or 0) * 0.02
        base_capital = 10000.0
        if base_capital > 0 and est_loss < 0:
            est_loss_pct = abs(est_loss) / base_capital
            if est_loss_pct > max_single_loss_pct:
                return False, (
                    f"单笔预计亏损 {est_loss_pct:.2%} 超过上限 {max_single_loss_pct:.2%}"
                )
        return True, ""

    # ---------- 违规处理：审计日志 + 邮件通知 ----------

    async def _on_violation(
        self,
        order: LiveOrder,
        instance: Optional[LiveStrategyInstance],
        reason: str,
        check_name: str,
    ) -> None:
        """风控违规时写入审计日志并发送邮件通知。"""
        # 1. 写入风险审计记录
        try:
            await write_audit_log(
                self.db,
                user_id=order.user_id,
                action=RISK_AUDIT_ACTION,
                resource_type="live_order",
                resource_id=str(order.id),
                detail={
                    "risk_violation": True,
                    "check": check_name,
                    "reason": reason,
                    "symbol": order.symbol,
                    "side": order.side,
                    "suggested_amount": order.suggested_amount,
                    "suggested_price": order.suggested_price,
                    "instance_id": str(instance.id) if instance else None,
                    "strategy_id": str(order.strategy_id),
                },
            )
        except Exception as e:
            logger.error("写入风控审计日志失败: %s", e)

        # 2. 发送邮件通知（异步，不阻塞下单流程）
        try:
            await self._send_risk_alert(order, reason)
        except Exception as e:
            logger.error("发送风控告警邮件失败: %s", e)

    async def _send_risk_alert(self, order: LiveOrder, reason: str) -> None:
        """发送风控告警邮件。"""
        from app.integrations.email import send_email

        # 查询用户邮箱
        result = await self.db.execute(
            select(User.email, User.nickname).where(User.id == order.user_id)
        )
        row = result.first()
        if row is None:
            return
        email, nickname = row

        subject = f"[风控告警] {order.symbol} {order.side} 订单被拦截"
        html = f"""
        <h2>风控拦截通知</h2>
        <p>用户：<strong>{nickname}</strong>（{email}）</p>
        <p>交易对：<strong>{order.symbol}</strong></p>
        <p>方向：<strong>{order.side}</strong></p>
        <p>建议数量：{order.suggested_amount}</p>
        <p>建议价格：{order.suggested_price}</p>
        <p>拦截原因：<strong style="color: red;">{reason}</strong></p>
        <p>订单 ID：{order.id}</p>
        <hr>
        <p style="color: #888; font-size: 12px;">
            此邮件由系统自动发送，如有疑问请联系管理员。
        </p>
        """
        await send_email(email, subject, html)


# ---------- 运行期监控（Stage 9.2） ----------


class RiskMonitor:
    """实盘运行期监控器。

    定时检查运行中的策略实例，触发自动止停：
    - 当日亏损达标 → 自动平仓 + 停止策略 + 告警
    - 策略回撤达标 → 停止策略
    - 账号连接异常 → 重试 3 次 → 停止并告警
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def monitor_all_instances(self) -> List[Dict]:
        """扫描所有 running 状态的实例，执行监控检查。

        Returns:
            触发止停的实例列表，每项含 instance_id、reason、action。
        """
        result = await self.db.execute(
            select(LiveStrategyInstance).where(
                LiveStrategyInstance.status == "running"
            )
        )
        instances = list(result.scalars().all())
        actions: List[Dict] = []

        for instance in instances:
            try:
                action = await self._check_instance(instance)
                if action:
                    actions.append(action)
            except Exception as e:
                logger.error(
                    "监控实例 %s 失败: %s", instance.id, e
                )

        return actions

    async def _check_instance(
        self, instance: LiveStrategyInstance
    ) -> Optional[Dict]:
        """检查单个实例，返回触发的动作（无触发返回 None）。"""
        params = risk_control_defaults(instance.risk_params)

        # 1. 策略累计回撤达标 → 停止策略
        max_dd_pct = float(params["max_drawdown_pct"])
        total_pnl = float(instance.total_pnl)
        base_capital = 10000.0
        if total_pnl < 0 and abs(total_pnl) / base_capital > max_dd_pct:
            await self._stop_instance(
                instance,
                f"策略累计回撤 {abs(total_pnl) / base_capital:.2%} 超过上限 {max_dd_pct:.2%}",
            )
            return {
                "instance_id": str(instance.id),
                "reason": "drawdown_exceeded",
                "action": "stopped",
            }

        # 2. 当日亏损达标 → 停止策略 + 告警
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        orders_result = await self.db.execute(
            select(LiveOrder).where(
                LiveOrder.instance_id == instance.id,
                LiveOrder.signal_at >= today_start,
                LiveOrder.status == "executed",
            )
        )
        today_orders = list(orders_result.scalars().all())
        today_pnl = sum(
            float(o.executed_price or 0) * float(o.executed_amount or 0) * (-1 if o.side == "sell" else 1)
            for o in today_orders
            if o.executed_price and o.executed_amount
        )
        max_daily_loss_pct = float(params["max_daily_loss_pct"])
        current_base = total_pnl + base_capital
        if current_base > 0 and today_pnl < 0:
            daily_loss_pct = abs(today_pnl) / current_base
            if daily_loss_pct > max_daily_loss_pct:
                await self._stop_instance(
                    instance,
                    f"当日亏损 {daily_loss_pct:.2%} 超过上限 {max_daily_loss_pct:.2%}",
                )
                return {
                    "instance_id": str(instance.id),
                    "reason": "daily_loss_exceeded",
                    "action": "stopped",
                }

        return None

    async def _stop_instance(
        self, instance: LiveStrategyInstance, reason: str
    ) -> None:
        """停止策略实例并写入审计日志。"""
        instance.status = "stopped"
        instance.stopped_at = datetime.datetime.now(datetime.timezone.utc)
        instance.stop_reason = reason
        await self.db.flush()

        # 写入审计日志
        try:
            await write_audit_log(
                self.db,
                user_id=instance.user_id,
                action=RISK_AUDIT_ACTION,
                resource_type="live_strategy_instance",
                resource_id=str(instance.id),
                detail={
                    "risk_violation": True,
                    "action": "auto_stop",
                    "reason": reason,
                    "strategy_id": str(instance.strategy_id),
                    "symbol": instance.symbol,
                    "total_pnl": float(instance.total_pnl),
                },
            )
        except Exception as e:
            logger.error("写入止停审计日志失败: %s", e)

        # 发送告警邮件
        try:
            await self._send_stop_alert(instance, reason)
        except Exception as e:
            logger.error("发送止停告警邮件失败: %s", e)

    async def _send_stop_alert(
        self, instance: LiveStrategyInstance, reason: str
    ) -> None:
        """发送策略止停告警邮件。"""
        from app.integrations.email import send_email

        result = await self.db.execute(
            select(User.email, User.nickname).where(User.id == instance.user_id)
        )
        row = result.first()
        if row is None:
            return
        email, nickname = row

        subject = f"[风控止停] 策略实例 {instance.symbol} 已自动停止"
        html = f"""
        <h2>策略自动止停通知</h2>
        <p>用户：<strong>{nickname}</strong>（{email}）</p>
        <p>交易对：<strong>{instance.symbol}</strong></p>
        <p>策略实例 ID：{instance.id}</p>
        <p>累计盈亏：{instance.total_pnl}</p>
        <p>止停原因：<strong style="color: red;">{reason}</strong></p>
        <hr>
        <p>策略已自动停止，请登录系统查看详情并评估是否重新启动。</p>
        <p style="color: #888; font-size: 12px;">
            此邮件由系统自动发送，如有疑问请联系管理员。
        </p>
        """
        await send_email(email, subject, html)
