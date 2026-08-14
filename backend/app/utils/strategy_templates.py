"""内置模板策略（Stage 6.2，对齐 PRD §5.6.1 R3）。

3 套内置模板：
1. 双均线金叉死叉（趋势追踪）
2. RSI 超买超卖反转（震荡反转）
3. 海龟突破（唐奇安通道 + ATR 止损 + 2N 加仓）

每套模板返回 StrategyDSL 结构，用于系统初始化写入 DB。
"""

from typing import Any, Dict

from app.schemas.strategy_dsl import (
    Condition,
    ConditionGroup,
    EntryRules,
    ExitRules,
    Pyramiding,
    RiskRules,
    SizingRules,
    StopLoss,
    StrategyDSL,
    TakeProfit,
    TimeStop,
    TrailingStop,
    TEMPLATE_STRATEGY_IDS,
)


def double_ma_template() -> Dict[str, Any]:
    """双均线金叉死叉策略（趋势追踪）。

    - 入场：MA5 上穿 MA20（金叉）
    - 出场：MA5 下穿 MA20（死叉）+ 5% 止损
    - 仓位：每次 10% 资金，最多 3 个持仓
    """
    dsl = StrategyDSL(
        entry=EntryRules(
            condition_group=ConditionGroup(
                logic="AND",
                conditions=[
                    Condition(
                        type="ma_cross",
                        params={"fast": 5, "slow": 20, "direction": "golden"},
                    ),
                ],
            ),
        ),
        exit=ExitRules(
            # 出场依赖入场信号的死叉，但保留止损兜底
            stop_loss=StopLoss(type="pct", value=0.05),
            time_stop=TimeStop(enabled=True, bars=100),
        ),
        sizing=SizingRules(
            method="fixed_pct",
            value=0.10,
            max_positions=3,
        ),
        risk_control=RiskRules(
            max_single_loss_pct=0.02,
            max_daily_loss_pct=0.05,
            max_consecutive_losses=5,
            max_drawdown_pct=0.20,
        ),
    )
    return {
        "id": TEMPLATE_STRATEGY_IDS["double_ma"],
        "name": "双均线金叉死叉（模板）",
        "category": "trend",
        "description": (
            "经典趋势追踪策略。MA5 上穿 MA20 买入（金叉），"
            "MA5 下穿 MA20 卖出（死叉）。适合趋势明显的市场。"
        ),
        "rules": dsl.to_dict(),
        "params": {"fast_period": 5, "slow_period": 20},
        "is_template": True,
    }


def rsi_reversal_template() -> Dict[str, Any]:
    """RSI 超买超卖反转策略（震荡反转）。

    - 入场：RSI < 30（超卖买入）
    - 出场：RSI > 70（超买卖出）+ 3% 止损
    - 仓位：每次 5% 资金
    """
    dsl = StrategyDSL(
        entry=EntryRules(
            condition_group=ConditionGroup(
                logic="AND",
                conditions=[
                    Condition(
                        type="rsi",
                        params={"period": 14, "max": 30},
                    ),
                ],
            ),
        ),
        exit=ExitRules(
            take_profit=TakeProfit(type="pct", value=0.08),
            stop_loss=StopLoss(type="pct", value=0.03),
            time_stop=TimeStop(enabled=True, bars=48),
        ),
        sizing=SizingRules(
            method="fixed_pct",
            value=0.05,
            max_positions=5,
        ),
        risk_control=RiskRules(
            max_single_loss_pct=0.015,
            max_daily_loss_pct=0.04,
            max_consecutive_losses=4,
            max_drawdown_pct=0.15,
        ),
    )
    return {
        "id": TEMPLATE_STRATEGY_IDS["rsi_reversal"],
        "name": "RSI 超买超卖反转（模板）",
        "category": "mean_reversion",
        "description": (
            "震荡反转策略。RSI 低于 30 时买入（超卖），"
            "RSI 高于 70 时卖出（超买）。适合震荡市场。"
        ),
        "rules": dsl.to_dict(),
        "params": {"rsi_period": 14, "oversold": 30, "overbought": 70},
        "is_template": True,
    }


def turtle_breakout_template() -> Dict[str, Any]:
    """海龟突破策略（唐奇安通道 + ATR 止损 + 2N 加仓）。

    - 入场：价格突破 20 日高点
    - 出场：价格跌破 10 日低点 + 2×ATR 止损
    - 仓位：每次 2% 风险（基于 ATR），最多加仓 3 次
    """
    dsl = StrategyDSL(
        entry=EntryRules(
            condition_group=ConditionGroup(
                logic="AND",
                conditions=[
                    Condition(
                        type="price_breakout",
                        params={"period": 20, "direction": "up"},
                    ),
                ],
            ),
        ),
        exit=ExitRules(
            # 海龟出场：跌破 10 日低点
            stop_loss=StopLoss(type="atr", multiplier=2.0),
            trailing_stop=TrailingStop(enabled=True, type="atr", multiplier=2.0),
            time_stop=TimeStop(enabled=False),
        ),
        sizing=SizingRules(
            method="fixed_pct",
            value=0.02,  # 单次风险 2%
            max_positions=4,
            pyramiding=Pyramiding(
                enabled=True,
                threshold_pct=0.005,  # 0.5% 盈利加仓
                size_pct=0.01,
                max_times=3,
            ),
        ),
        risk_control=RiskRules(
            max_single_loss_pct=0.02,
            max_daily_loss_pct=0.05,
            max_consecutive_losses=5,
            max_drawdown_pct=0.20,
        ),
    )
    return {
        "id": TEMPLATE_STRATEGY_IDS["turtle_breakout"],
        "name": "海龟突破（模板）",
        "category": "breakout",
        "description": (
            "经典海龟交易法。价格突破 20 日高点买入，"
            "2×ATR 止损，跌破 10 日低点卖出。"
            "支持盈利加仓（最多 3 次）。适合强趋势市场。"
        ),
        "rules": dsl.to_dict(),
        "params": {
            "entry_period": 20,
            "exit_period": 10,
            "atr_period": 20,
            "atr_multiplier": 2.0,
        },
        "is_template": True,
    }


def all_templates() -> list:
    """返回全部 3 套模板策略。"""
    return [
        double_ma_template(),
        rsi_reversal_template(),
        turtle_breakout_template(),
    ]
