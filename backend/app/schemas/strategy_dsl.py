"""策略 DSL Schema（Stage 6.1，对齐 PRD §5.6.2）。

策略规则结构化定义，支持 3 层 AND/OR 嵌套：
- 入场规则（EntryRules）：技术条件 + 逻辑组合 + 时间过滤 + 多周期共振
- 出场规则（ExitRules）：止盈 / 止损 / 移动止损 / 时间止损
- 仓位管理（SizingRules）：固定手数 / 固定金额 / 固定比例 / 凯利公式 / 加仓
- 风控参数（RiskRules）：单笔/每日最大亏损、最大持仓、连续亏损

JSON 结构示例（存入 Strategy.rules）：
{
  "entry": {
    "logic": "AND",
    "conditions": [
      {"type": "ma_cross", "fast": 5, "slow": 20, "direction": "golden"},
      {"type": "rsi", "period": 14, "min": 30, "max": 70}
    ],
    "groups": [
      {
        "logic": "OR",
        "conditions": [...],
        "groups": []
      }
    ]
  },
  "exit": {
    "take_profit": {"type": "pct", "value": 0.1},
    "stop_loss": {"type": "atr", "multiplier": 2.0},
    "trailing_stop": {"type": "atr", "multiplier": 1.5},
    "time_stop": {"bars": 48}
  },
  "sizing": {
    "method": "fixed_pct",
    "value": 0.02,
    "max_positions": 5,
    "pyramiding": {"enabled": true, "threshold_pct": 0.05, "size_pct": 0.01, "max_times": 3}
  },
  "risk_control": {
    "max_single_loss_pct": 0.02,
    "max_daily_loss_pct": 0.05,
    "max_consecutive_losses": 5,
    "max_drawdown_pct": 0.20
  }
}
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ---------- 条件定义 ----------

class Condition(BaseModel):
    """单个技术条件。

    type 决定使用哪些参数，常见类型：
    - ma_cross: 均线交叉（fast/slow/direction: golden|death）
    - rsi: RSI 阈值（period/min/max）
    - macd: MACD 金叉死叉（fast/slow/signal/direction: golden|death）
    - price_breakout: 价格突破（period/direction: up|down）
    - atr_breakout: ATR 倍数突破（period/multiplier/direction）
    - boll_touch: 布林带触及（period/std/band: upper|lower）
    - kdj_cross: KDJ 金叉死叉（period/direction）
    """

    type: str = Field(..., description="条件类型")
    # 通用参数容器（不同 type 使用不同字段）
    params: Dict[str, Any] = Field(default_factory=dict, description="条件参数")


class ConditionGroup(BaseModel):
    """条件组（支持 3 层 AND/OR 嵌套）。

    评估逻辑：先评估 conditions 列表，再评估 groups 列表，
    按 logic（AND/OR）组合结果。
    """

    logic: str = Field("AND", description="逻辑组合：AND / OR")
    conditions: List[Condition] = Field(default_factory=list, description="条件列表")
    groups: List["ConditionGroup"] = Field(default_factory=list, description="嵌套条件组（最多 3 层）")

    @model_validator(mode="after")
    def _validate_depth(self) -> "ConditionGroup":
        """校验嵌套深度不超过 3 层。"""
        depth = self._calc_depth()
        if depth > 3:
            raise ValueError(f"条件组嵌套深度 {depth} 超过最大值 3")
        return self

    def _calc_depth(self) -> int:
        if not self.groups:
            return 1
        return 1 + max(g._calc_depth() for g in self.groups)

    @model_validator(mode="after")
    def _validate_logic(self) -> "ConditionGroup":
        if self.logic not in ("AND", "OR"):
            raise ValueError(f"logic 必须为 AND 或 OR，当前: {self.logic}")
        return self


# 解决前向引用
ConditionGroup.model_rebuild()


# ---------- 入场规则 ----------

class TimeFilter(BaseModel):
    """时间过滤（只在某时段/星期交易）。"""

    enabled: bool = False
    weekdays: Optional[List[int]] = Field(
        None, description="允许交易的星期（0=周一 ... 6=周日）"
    )
    hours: Optional[List[int]] = Field(None, description="允许交易的小时（0-23）")


class MultiTimeframeConfirm(BaseModel):
    """多周期共振确认。"""

    enabled: bool = False
    timeframes: List[str] = Field(
        default_factory=lambda: ["4h", "1d"],
        description="需要共振的周期列表",
    )
    direction: str = Field("same", description="same: 同方向; any: 任一方向")


class EntryRules(BaseModel):
    """入场规则。"""

    condition_group: ConditionGroup = Field(
        default_factory=lambda: ConditionGroup(logic="AND", conditions=[], groups=[]),
        description="入场条件组",
    )
    time_filter: Optional[TimeFilter] = None
    multi_timeframe: Optional[MultiTimeframeConfirm] = None


# ---------- 出场规则 ----------

class TakeProfit(BaseModel):
    """止盈规则。"""

    type: str = Field("pct", description="pct: 固定比例; atr: ATR 倍数; ma: MA 反向穿越")
    value: Optional[float] = Field(None, description="type=pct 时为止盈比例（如 0.1=10%）")
    multiplier: Optional[float] = Field(None, description="type=atr 时为 ATR 倍数")
    ma_period: Optional[int] = Field(None, description="type=ma 时为 MA 周期")


class StopLoss(BaseModel):
    """止损规则。"""

    type: str = Field("pct", description="pct: 固定比例; atr: ATR 倍数; recent_high_low: 近期高低点")
    value: Optional[float] = Field(None, description="type=pct 时为止损比例")
    multiplier: Optional[float] = Field(None, description="type=atr 时为 ATR 倍数")
    lookback: Optional[int] = Field(None, description="type=recent_high_low 时为回看周期")


class TrailingStop(BaseModel):
    """移动止损。"""

    enabled: bool = False
    type: str = Field("atr", description="atr: ATR 倍数; pct: 固定比例")
    multiplier: Optional[float] = Field(None, description="type=atr 时为 ATR 倍数")
    value: Optional[float] = Field(None, description="type=pct 时为比例")


class TimeStop(BaseModel):
    """时间止损（持仓超过 N 周期强制平仓）。"""

    enabled: bool = False
    bars: int = Field(48, description="最大持仓周期数")


class ExitRules(BaseModel):
    """出场规则。"""

    take_profit: Optional[TakeProfit] = None
    stop_loss: Optional[StopLoss] = None
    trailing_stop: Optional[TrailingStop] = None
    time_stop: Optional[TimeStop] = None


# ---------- 仓位管理 ----------

class Pyramiding(BaseModel):
    """加仓规则。"""

    enabled: bool = False
    threshold_pct: float = Field(0.05, description="浮盈达到 X% 触发加仓")
    size_pct: float = Field(0.01, description="每次加仓比例")
    max_times: int = Field(3, description="最多加仓次数")


class SizingRules(BaseModel):
    """仓位管理规则。"""

    method: str = Field(
        "fixed_pct",
        description="fixed_amount: 固定金额; fixed_pct: 固定比例; kelly: 凯利公式",
    )
    value: float = Field(0.02, description="method 对应的值（比例或金额）")
    max_positions: int = Field(5, description="最大同时持仓数")
    pyramiding: Optional[Pyramiding] = None


# ---------- 风控参数 ----------

class RiskRules(BaseModel):
    """风控参数（对齐 PRD §9.2 八阈值中策略级）。"""

    max_single_loss_pct: float = Field(0.02, description="单笔最大亏损占总资金 %")
    max_daily_loss_pct: float = Field(0.05, description="每日最大亏损占总资金 %")
    max_consecutive_losses: int = Field(5, description="最大连续亏损次数")
    max_drawdown_pct: float = Field(0.20, description="策略最大回撤 %")
    max_holdings_per_symbol: int = Field(2, description="同币种最大持仓数")
    max_total_holdings: int = Field(10, description="总最大持仓数")


# ---------- 策略 DSL 顶层 ----------

class StrategyDSL(BaseModel):
    """策略 DSL 顶层结构（4 大核心组成，对齐 PRD §5.6.1 R1）。

    存入 Strategy.rules 字段（JSONB）。
    """

    entry: EntryRules = Field(default_factory=EntryRules)
    exit: ExitRules = Field(default_factory=ExitRules)
    sizing: SizingRules = Field(default_factory=SizingRules)
    risk_control: RiskRules = Field(default_factory=RiskRules)

    @classmethod
    def from_strategy_rules(cls, rules: Optional[Dict[str, Any]]) -> "StrategyDSL":
        """从 Strategy.rules 字典构建 DSL（兼容旧格式）。"""
        if not rules:
            return cls()
        try:
            return cls.model_validate(rules)
        except Exception:
            # 旧格式 rules 无法解析时返回默认
            return cls()

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（存入 Strategy.rules）。"""
        return self.model_dump(mode="json", exclude_none=True)


# ---------- 策略模板标识 ----------

# 内置模板策略的 category 标识
STRATEGY_CATEGORY_TREND = "trend"
STRATEGY_CATEGORY_MEAN_REVERSION = "mean_reversion"
STRATEGY_CATEGORY_BREAKOUT = "breakout"
STRATEGY_CATEGORY_GRID = "grid"
STRATEGY_CATEGORY_ARBITRAGE = "arbitrage"
STRATEGY_CATEGORY_CUSTOM = "custom"

# 内置模板策略的固定 ID（用于系统初始化）
TEMPLATE_STRATEGY_IDS = {
    "double_ma": "00000000-0000-0000-0000-000000000001",
    "rsi_reversal": "00000000-0000-0000-0000-000000000002",
    "turtle_breakout": "00000000-0000-0000-0000-000000000003",
}
