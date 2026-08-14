"""AI 回测决策执行器。"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DecisionExecutor:
    """根据 AI 或规则引擎的决策执行开仓/平仓/持有。

    核心职责：
    - 强制执行三条策略前提规则（单仓规则、强制止损、严格执规）
    - 根据 AI 决策或规则引擎结果执行交易动作
    """

    def __init__(self, ctx):
        """
        Args:
            ctx: AIBacktestContext 实例
        """
        self.ctx = ctx

    def execute(
        self,
        kline: Dict[str, Any],
        ai_result: Optional[Dict[str, Any]],
        indicators: Dict[str, Any],
    ):
        """执行决策（强制执行策略前提规则）。"""
        # 获取策略前提规则
        prerequisites = self.ctx.strategy_rules.get("prerequisites", {})
        single_position_enabled = prerequisites.get("single_position", {}).get("enabled", True)
        mandatory_sl_enabled = prerequisites.get("mandatory_stop_loss", {}).get("enabled", True)
        default_sl_pct = prerequisites.get("mandatory_stop_loss", {}).get("default_stop_loss_pct", 0.03)

        if ai_result:
            decision = ai_result.get("decision", "hold")
            trade_plan = ai_result.get("trade_plan", {})
        else:
            decision, trade_plan = self._rule_engine(kline, indicators)

        if decision == "hold" or decision == "no_action":
            return

        if decision in ("open_long", "open_short"):
            # 规则 1：单仓规则 - 有持仓时禁止开仓
            if single_position_enabled and self.ctx.current_position:
                logger.warning(f"[单仓规则] 已有持仓，忽略开仓信号: {decision}")
                return

            # 规则 2：强制止损 - 开仓时必须设置止损
            trade_plan = self._ensure_stop_loss(
                trade_plan, kline, decision, mandatory_sl_enabled, default_sl_pct
            )
            self._open_position(decision, kline, trade_plan, ai_result)

        elif decision in ("close_long", "close_short"):
            self._close_position(decision, kline, trade_plan, ai_result)

    def _ensure_stop_loss(
        self, trade_plan: Dict, kline: Dict, decision: str,
        mandatory_sl_enabled: bool, default_sl_pct: float,
    ) -> Dict:
        """确保止损设置（强制执行规则 2）。"""
        if not mandatory_sl_enabled:
            return trade_plan

        entry_price = trade_plan.get("entry_price") or kline["close"]
        stop_loss = trade_plan.get("stop_loss")

        if stop_loss is not None:
            return trade_plan

        # AI 未提供止损，自动计算
        is_long = "long" in decision
        if is_long:
            auto_sl = entry_price * (1 - default_sl_pct)
        else:
            auto_sl = entry_price * (1 + default_sl_pct)

        trade_plan["stop_loss"] = auto_sl
        trade_plan["stop_loss_auto"] = True
        logger.warning(
            f"[强制止损] AI 未提供止损，自动按 {default_sl_pct*100}% 计算: {auto_sl}"
        )
        return trade_plan

    def _open_position(
        self, decision: str, kline: Dict[str, Any],
        trade_plan: Dict[str, Any], ai_result: Optional[Dict[str, Any]],
    ):
        """开仓。"""
        if self.ctx.current_position:
            logger.warning("已有持仓，无法开仓")
            return

        direction = "long" if "long" in decision else "short"
        entry_price = trade_plan.get("entry_price") or kline["close"]
        quantity = trade_plan.get("quantity") or self._calculate_quantity(entry_price)
        stop_loss = trade_plan.get("stop_loss")
        take_profit = trade_plan.get("take_profit")

        # 风控校验
        risk_amount = abs(entry_price - stop_loss) * quantity if stop_loss else 0
        max_risk = self.ctx.initial_capital * 0.02
        if risk_amount > max_risk:
            logger.warning(f"风控拦截：单笔风险 {risk_amount} > 最大 {max_risk}")
            return

        # 更新持仓状态
        self.ctx.current_position = {
            "direction": direction,
            "entry_price": entry_price,
            "quantity": quantity,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "entry_kline_index": self.ctx.current_kline_index,
            "holding_bars": 0,
            "unrealized_pnl": 0.0,
        }

        # 扣除资金
        cost = entry_price * quantity
        self.ctx.available_cash -= cost

        # 记录交易
        trade = {
            "index": self.ctx.total_trades + 1,
            "direction": direction,
            "entry_time": kline["timestamp"],
            "entry_price": entry_price,
            "quantity": quantity,
            "open_ai_analysis": json.dumps(ai_result, ensure_ascii=False) if ai_result else None,
            "open_reason": trade_plan.get("reason", ""),
            "open_confidence": trade_plan.get("confidence"),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "fee": cost * self.ctx.fee_rate,
        }
        self.ctx.current_trade = trade
        self.ctx.total_trades += 1

    def _close_position(
        self, decision: str, kline: Dict[str, Any],
        trade_plan: Dict[str, Any], ai_result: Optional[Dict[str, Any]],
    ):
        """平仓。"""
        if not self.ctx.current_position:
            return

        position = self.ctx.current_position
        exit_price = kline["close"]
        exit_reason = trade_plan.get("reason", "AI 决策平仓")

        # 计算盈亏
        if position["direction"] == "long":
            pnl = (exit_price - position["entry_price"]) * position["quantity"]
        else:
            pnl = (position["entry_price"] - exit_price) * position["quantity"]

        # 扣除手续费
        exit_fee = exit_price * position["quantity"] * self.ctx.fee_rate
        pnl -= exit_fee
        pnl -= position.get("fee", 0)

        # 更新账户
        self.ctx.current_equity += pnl
        self.ctx.available_cash = self.ctx.current_equity

        # 记录平仓
        trade = self.ctx.current_trade or {}
        trade.update({
            "exit_time": kline["timestamp"],
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "exit_ai_analysis": json.dumps(ai_result, ensure_ascii=False) if ai_result else None,
            "exit_confidence": trade_plan.get("confidence"),
            "holding_bars": self.ctx.current_kline_index - position.get("entry_kline_index", 0),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl / (position["entry_price"] * position["quantity"]) * 100, 2),
        })

        self.ctx.completed_trades.append(trade)
        self.ctx.current_trade = None
        self.ctx.current_position = None

    def _calculate_quantity(self, price: float) -> float:
        """根据仓位管理计算开仓数量。"""
        capital_used = self.ctx.available_cash * 0.3
        return round(capital_used / price, 8)

    def _rule_engine(
        self, kline: Dict[str, Any], indicators: Dict[str, Any]
    ) -> tuple:
        """规则引擎降级方案（简化版）。"""
        close = kline["close"]
        ma5 = indicators.get("ma5", close)
        ma10 = indicators.get("ma10", close)
        rsi = indicators.get("rsi_14", 50)

        if close > ma5 and ma5 > ma10 and rsi < 70:
            if not self.ctx.current_position:
                return ("open_long", {
                    "reason": "规则引擎：均线多头排列，RSI 未超买",
                    "confidence": 3,
                    "entry_price": close,
                    "stop_loss": close * 0.97,
                    "take_profit": close * 1.05,
                })
        elif close < ma5 and ma5 < ma10 and rsi > 30:
            if self.ctx.current_position:
                return ("close_long", {
                    "reason": "规则引擎：均线死叉，平仓离场",
                    "confidence": 3,
                })

        return ("hold", {})