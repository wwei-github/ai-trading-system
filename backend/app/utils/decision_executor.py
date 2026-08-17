"""AI 回测决策执行器。"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DecisionExecutor:
    """根据 AI 或规则引擎的决策执行开仓/平仓/持有。

    核心职责：
    - 强制执行三条策略前提规则（单仓规则、强制止损、严格执规）
    - 根据 AI 决策或规则引擎结果执行交易动作
    - 规则引擎根据策略的 entry_rules / exit_rules 动态评估
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
            # AI 不可用时 —— 仅处理已有持仓的平仓/止损，不开新仓
            if self.ctx.current_position:
                decision, trade_plan = self._rule_engine_exit_only(kline, indicators)
            else:
                decision, trade_plan = "hold", {}

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
            "source_strategy": ai_result.get("source_strategy", "") if ai_result else "",
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

    # ==================== 策略规则引擎 ====================

    def _rule_engine_exit_only(
        self, kline: Dict[str, Any], indicators: Dict[str, Any]
    ) -> Tuple[str, Dict]:
        """AI 不可用时，仅处理已有持仓的平仓/止损，不开新仓。"""
        if not self.ctx.current_position:
            return ("hold", {})

        # 止损/止盈检查（硬止损）
        exit_decision = self._check_position_exit(kline)
        if exit_decision[0] != "hold":
            return exit_decision

        # 策略出场规则检查
        exit_rules = self.ctx.strategy_rules.get("exit_rules", [])
        if exit_rules:
            result = self._evaluate_rules(exit_rules, kline, indicators, "exit")
            if result[0] != "hold":
                return result

        return ("hold", {})

    def _rule_engine(
        self, kline: Dict[str, Any], indicators: Dict[str, Any]
    ) -> Tuple[str, Dict]:
        """根据策略的 entry_rules / exit_rules 动态评估决策。

        流程：
        1. 无持仓时，检查 entry_rules 是否满足开仓条件
        2. 有持仓时，检查 exit_rules 是否满足平仓条件
        3. 同时检查强制止损/止盈
        """
        # 检查持仓止损/止盈（优先于规则）
        if self.ctx.current_position:
            exit_decision = self._check_position_exit(kline)
            if exit_decision[0] != "hold":
                return exit_decision

        # 检查策略入场规则
        entry_rules = self.ctx.strategy_rules.get("entry_rules", [])
        if not self.ctx.current_position and entry_rules:
            result = self._evaluate_rules(entry_rules, kline, indicators, "entry")
            if result[0] != "hold":
                return result

        # 检查策略出场规则
        exit_rules = self.ctx.strategy_rules.get("exit_rules", [])
        if self.ctx.current_position and exit_rules:
            result = self._evaluate_rules(exit_rules, kline, indicators, "exit")
            if result[0] != "hold":
                return result

        return ("hold", {})

    def _check_position_exit(self, kline: Dict) -> Tuple[str, Dict]:
        """检查持仓止损/止盈条件。"""
        pos = self.ctx.current_position
        if not pos:
            return ("hold", {})

        high = kline["high"]
        low = kline["low"]
        direction = pos["direction"]
        stop_loss = pos.get("stop_loss")
        take_profit = pos.get("take_profit")

        # 止损检查（用 high/low 判断，避免 intra-bar 穿价未触发）
        if stop_loss is not None:
            if direction == "long" and low <= stop_loss:
                return ("close_long", {"reason": "策略规则：触及止损位，平仓离场", "confidence": 5})
            if direction == "short" and high >= stop_loss:
                return ("close_short", {"reason": "策略规则：触及止损位，平仓离场", "confidence": 5})

        # 止盈检查（用 high/low 判断，避免 intra-bar 穿价未触发）
        if take_profit is not None:
            if direction == "long" and high >= take_profit:
                return ("close_long", {"reason": "策略规则：触及止盈位，平仓离场", "confidence": 5})
            if direction == "short" and low <= take_profit:
                return ("close_short", {"reason": "策略规则：触及止盈位，平仓离场", "confidence": 5})

        return ("hold", {})

    def _evaluate_rules(
        self, rules: list, kline: Dict, indicators: Dict, rule_type: str
    ) -> Tuple[str, Dict]:
        """评估策略规则组。

        规则组之间为 OR 逻辑（任一满足即可）。
        组内条件之间为 logic 指定的逻辑（AND/OR）。
        """
        for rule_group in rules:
            logic = rule_group.get("logic", "AND")
            conditions = rule_group.get("conditions", [])

            if rule_type == "entry":
                matched = self._evaluate_entry_group(conditions, logic, kline, indicators)
            else:
                matched = self._evaluate_exit_group(conditions, logic, kline, indicators)

            if matched:
                return matched

        return ("hold", {})

    def _evaluate_entry_group(
        self, conditions: list, logic: str, kline: Dict, indicators: Dict
    ) -> Optional[Tuple[str, Dict]]:
        """评估一组入场条件，返回决策和匹配的具体条件。"""
        results = []
        for cond in conditions:
            result = self._evaluate_condition(cond, kline, indicators)
            results.append(result)

        if logic == "AND":
            if all(r.indicators.get("matched", False) for r in results):
                matched_conditions = [r.condition for r in results if r.indicators.get("matched")]
                return self._build_entry_decision(kline, indicators, matched_conditions)
        elif logic == "OR":
            matched = [r for r in results if r.indicators.get("matched")]
            if matched:
                matched_conditions = [r.condition for r in matched]
                return self._build_entry_decision(kline, indicators, matched_conditions)

        return None

    def _evaluate_exit_group(
        self, conditions: list, logic: str, kline: Dict, indicators: Dict
    ) -> Optional[Tuple[str, Dict]]:
        """评估一组出场条件。"""
        pos = self.ctx.current_position
        if not pos:
            return None

        results = []
        exit_reason = None
        for cond in conditions:
            result, reason = self._evaluate_exit_condition(cond, kline, indicators)
            results.append(result)
            if result:
                exit_reason = reason

        if logic == "AND":
            if all(results):
                return self._build_exit_decision(pos["direction"], exit_reason or "策略规则出场")
        elif logic == "OR":
            if any(results):
                return self._build_exit_decision(pos["direction"], exit_reason or "策略规则出场")

        return None

    def _evaluate_condition(self, cond: dict, kline: Dict, indicators: Dict) -> Dict:
        """评估单个入场条件，返回匹配结果和条件信息。"""
        indicator = cond.get("indicator", "")
        operator = cond.get("operator", "=")
        value = cond.get("value", "")

        close = kline["close"]
        open_price = kline["open"]
        high = kline["high"]
        low = kline["low"]
        volume = kline.get("volume", 0)

        # 基础结果结构
        def _result(matched: bool) -> Dict:
            return {"matched": matched, "condition": cond, "indicator": indicator, "value": value}

        # ---- 趋势过滤 ----
        if indicator == "trend_filter":
            ema20 = indicators.get("ema20", close)
            ema50 = indicators.get("ema50", close)
            if value == "uptrend":
                return _result(close > ema20 and ema20 > ema50)
            elif value == "downtrend":
                return _result(close < ema20 and ema20 < ema50)
            return _result(False)

        # ---- Pinbar 信号 ----
        if indicator == "pinbar_signal":
            body = abs(close - open_price)
            lower_wick = min(open_price, close) - low
            upper_wick = high - max(open_price, close)
            total_range = high - low
            if total_range == 0:
                return _result(False)

            if value == "bullish_pinbar":
                matched = (lower_wick > body * 2
                           and lower_wick > upper_wick
                           and body < total_range * 0.4)
                if matched:
                    return {
                        "matched": True, "condition": cond,
                        "indicator": "pinbar_signal", "value": "bullish_pinbar",
                        "pinbar": {"body": body, "lower_wick": lower_wick,
                                   "upper_wick": upper_wick, "low": low, "high": high,
                                   "close": close, "open": open_price},
                    }
                return _result(False)
            elif value == "bearish_pinbar":
                matched = (upper_wick > body * 2
                           and upper_wick > lower_wick
                           and body < total_range * 0.4)
                if matched:
                    return {
                        "matched": True, "condition": cond,
                        "indicator": "pinbar_signal", "value": "bearish_pinbar",
                        "pinbar": {"body": body, "lower_wick": lower_wick,
                                   "upper_wick": upper_wick, "low": low, "high": high,
                                   "close": close, "open": open_price},
                    }
                return _result(False)
            return _result(False)

        # ---- 成交量确认 ----
        if indicator == "volume":
            volume_ma = indicators.get("volume_ma20", volume)
            if operator == ">" and value == "average_volume":
                return _result(volume > volume_ma)
            return _result(False)

        # ---- 反向信号 ----
        if indicator == "reverse_signal":
            if value == "opposite_pinbar":
                body = abs(close - open_price)
                lower_wick = min(open_price, close) - low
                upper_wick = high - max(open_price, close)
                total_range = high - low
                if total_range == 0:
                    return _result(False)
                pos = self.ctx.current_position
                if pos and pos["direction"] == "long":
                    matched = (upper_wick > body * 2
                               and upper_wick > lower_wick
                               and body < total_range * 0.4)
                    if matched:
                        return {
                            "matched": True, "condition": cond,
                            "indicator": "reverse_signal", "value": "opposite_pinbar",
                            "direction": "close_long",
                            "pinbar": {"body": body, "lower_wick": lower_wick,
                                       "upper_wick": upper_wick, "low": low, "high": high,
                                       "close": close, "open": open_price},
                        }
                elif pos and pos["direction"] == "short":
                    matched = (lower_wick > body * 2
                               and lower_wick > upper_wick
                               and body < total_range * 0.4)
                    if matched:
                        return {
                            "matched": True, "condition": cond,
                            "indicator": "reverse_signal", "value": "opposite_pinbar",
                            "direction": "close_short",
                            "pinbar": {"body": body, "lower_wick": lower_wick,
                                       "upper_wick": upper_wick, "low": low, "high": high,
                                       "close": close, "open": open_price},
                        }
            return _result(False)

        # ---- 移动止损 ----
        if indicator == "trailing_stop":
            if value == "ema20_cross":
                ema20 = indicators.get("ema20", close)
                pos = self.ctx.current_position
                if pos and pos["direction"] == "long":
                    return _result(close < ema20)
                elif pos and pos["direction"] == "short":
                    return _result(close > ema20)
            return _result(False)

        # ---- 未知条件 ----
        logger.warning(f"规则引擎遇到未知条件: {indicator}={value}")
        return _result(False)

    def _evaluate_exit_condition(self, cond: dict, kline: Dict, indicators: Dict) -> Tuple[bool, str]:
        """评估单个出场条件。"""
        indicator = cond.get("indicator", "")
        value = cond.get("value", "")

        close = kline["close"]
        open_price = kline["open"]
        high = kline["high"]
        low = kline["low"]
        volume = kline.get("volume", 0)
        pos = self.ctx.current_position

        if not pos:
            return (False, "")

        # ---- 止损/止盈已在 _check_position_exit 中处理，这里通过规则描述匹配 ----
        if indicator == "stop_loss" and value == "pinbar_extreme":
            stop_loss = pos.get("stop_loss")
            if stop_loss is not None:
                if pos["direction"] == "long" and low <= stop_loss:
                    return (True, "策略规则：Pinbar极值止损")
                if pos["direction"] == "short" and high >= stop_loss:
                    return (True, "策略规则：Pinbar极值止损")
            return (False, "")

        if indicator == "take_profit" and value in ("1.5R_or_2R",):
            take_profit = pos.get("take_profit")
            if take_profit is not None:
                if pos["direction"] == "long" and high >= take_profit:
                    return (True, "策略规则：止盈目标1.5R~2R")
                if pos["direction"] == "short" and low <= take_profit:
                    return (True, "策略规则：止盈目标1.5R~2R")
            return (False, "")

        # ---- 反向 Pinbar 信号 ----
        if indicator == "reverse_signal" and value == "opposite_pinbar":
            body = abs(close - open_price)
            lower_wick = min(open_price, close) - low
            upper_wick = high - max(open_price, close)
            total_range = high - low
            if total_range == 0:
                return (False, "")
            if pos["direction"] == "long":
                is_bearish = (upper_wick > body * 2
                              and upper_wick > lower_wick
                              and body < total_range * 0.4)
                if is_bearish:
                    return (True, "策略规则：出现反向Pinbar信号，平仓离场")
            elif pos["direction"] == "short":
                is_bullish = (lower_wick > body * 2
                              and lower_wick > upper_wick
                              and body < total_range * 0.4)
                if is_bullish:
                    return (True, "策略规则：出现反向Pinbar信号，平仓离场")
            return (False, "")

        # ---- EMA20 移动止损 ----
        if indicator == "trailing_stop" and value == "ema20_cross":
            ema20 = indicators.get("ema20", close)
            if pos["direction"] == "long" and close < ema20:
                return (True, "策略规则：价格跌破EMA20，移动止损离场")
            if pos["direction"] == "short" and close > ema20:
                return (True, "策略规则：价格突破EMA20，移动止损离场")
            return (False, "")

        return (False, "")

    def _build_entry_decision(self, kline: Dict, indicators: Dict,
                              matched_conditions: Optional[List[Dict]] = None) -> Tuple[str, Dict]:
        """根据匹配的策略规则条件构建开仓决策。

        Args:
            kline: 当前 K 线
            indicators: 技术指标
            matched_conditions: 匹配的具体条件列表（含 indicator/value/pinbar 等字段）

        Returns:
            (decision, trade_plan) 元组
        """
        close = kline["close"]
        direction = None
        direction_source = None  # 用于生成开仓理由
        stop_loss = None
        take_profit = None
        entry_price = close

        # 收集匹配的 Pinbar 信息
        pinbar_info = None
        has_trend_filter = False
        trend_filter_direction = None

        for cond_info in (matched_conditions or []):
            indicator = cond_info.get("indicator", "")
            value = cond_info.get("value", "")

            if indicator == "pinbar_signal":
                pinbar_info = cond_info.get("pinbar", {})
                if value == "bullish_pinbar":
                    direction = "long"
                    direction_source = "看涨Pinbar"
                    # Pinbar 止损：下影线最低点下方
                    stop_loss = pinbar_info["low"] - (pinbar_info["high"] - pinbar_info["low"]) * 0.05
                    # Pinbar 止盈：1.5R
                    risk = entry_price - stop_loss
                    take_profit = entry_price + risk * 1.5
                elif value == "bearish_pinbar":
                    direction = "short"
                    direction_source = "看跌Pinbar"
                    # Pinbar 止损：上影线最高点上方
                    stop_loss = pinbar_info["high"] + (pinbar_info["high"] - pinbar_info["low"]) * 0.05
                    # Pinbar 止盈：1.5R
                    risk = stop_loss - entry_price
                    take_profit = entry_price - risk * 1.5

            elif indicator == "trend_filter":
                has_trend_filter = True
                if value == "uptrend":
                    trend_filter_direction = "long"
                elif value == "downtrend":
                    trend_filter_direction = "short"

        # 方向决策：Pinbar 信号优先，其次趋势过滤
        if direction is None:
            if has_trend_filter and trend_filter_direction:
                direction = trend_filter_direction
                direction_source = f"{trend_filter_direction}趋势过滤"
                # 趋势过滤方向：默认 3% 止损，5% 止盈
                if direction == "long":
                    stop_loss = close * 0.97
                    take_profit = close * 1.05
                else:
                    stop_loss = close * 1.03
                    take_profit = close * 0.95
            else:
                # 回退：根据 EMA 趋势判断（仅当无具体条件匹配时）
                ema20 = indicators.get("ema20", close)
                ema50 = indicators.get("ema50", close)
                if close > ema20 and ema20 > ema50:
                    direction = "long"
                    direction_source = "EMA多头排列"
                    stop_loss = close * 0.97
                    take_profit = close * 1.05
                elif close < ema20 and ema20 < ema50:
                    direction = "short"
                    direction_source = "EMA空头排列"
                    stop_loss = close * 1.03
                    take_profit = close * 0.95
                else:
                    # 盘整行情，默认做多
                    direction = "long"
                    direction_source = "默认方向（盘整）"
                    stop_loss = close * 0.97
                    take_profit = close * 1.05

        # 构建开仓理由
        if pinbar_info:
            reason = (
                f"策略规则：{direction_source}信号触发，"
                f"Pinbar实体={pinbar_info['body']:.2f} 下影线={pinbar_info['lower_wick']:.2f} "
                f"上影线={pinbar_info['upper_wick']:.2f}，"
                f"止损Pinbar极值，止盈1.5R"
            )
        else:
            reason = f"策略规则：{direction_source}信号触发，止损{abs(1-stop_loss/close)*100:.0f}%，止盈{abs(take_profit/close-1)*100:.0f}%"

        return (f"open_{direction}", {
            "reason": reason,
            "confidence": 4,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        })

    def _build_exit_decision(self, direction: str, reason: str) -> Tuple[str, Dict]:
        """构建平仓决策。"""
        return (f"close_{direction}", {
            "reason": reason,
            "confidence": 4,
        })