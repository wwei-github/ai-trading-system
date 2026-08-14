# AI 回测 K 线分析优化 - 后端技术方案

## 1. 概述

基于架构设计文档，实现 AI 回测核心逻辑优化，包括两级 AI 过滤机制（主AI粗略预筛 或 本地模型预筛）、持仓免分析、K 线窗口限制、多策略融合优化。

---

## 2. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/ai_backtest.py` | 修改 | 新增 `parent_backtest_id`、`strategy_ids`、`use_local_model`、`local_model_klines` 字段 |
| `backend/app/models/ai_backtest_trade.py` | 修改 | 新增 `ai_window_start`、`ai_window_end` 字段 |
| `backend/app/schemas/ai_backtest.py` | 修改 | 新增对应字段的 Schema 定义 |
| `backend/app/tasks/ai_backtest_tasks.py` | 修改 | 主循环逻辑重写：两级 AI 过滤 + 持仓免分析 + 本地模型分支 |
| `backend/app/utils/ai_market_analyzer.py` | 修改 | 新增 `quick_precheck()` AI粗略预筛方法；新增 `analyze_with_window()` 深度分析方法 |
| `backend/app/utils/local_model_prechecker.py` | **新增** | 本地模型预筛器，调用 Ollama 分析少量 K 线 |
| `backend/app/services/ai_backtest_service.py` | 修改 | 新增 `merge_optimize()` 多策略融合优化方法 |
| `backend/app/api/v1/ai_backtest_routes.py` | 修改 | 新增多策略融合 API 路由 |
| `backend/alembic/versions/` | 新增 | 数据库迁移脚本 |

---

## 3. 数据库模型变更

### 3.1 AIBacktest 模型

```python
# backend/app/models/ai_backtest.py

class AIBacktest(Base):
    __tablename__ = "ai_backtests"

    # ... 现有字段保持不变 ...

    # 新增字段
    parent_backtest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_backtests.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="父回测 ID（多策略融合时使用）"
    )
    strategy_ids: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, comment="参与回测的策略 ID 列表"
    )
    ai_call_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0, comment="AI 调用总次数"
    )
    precheck_total: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0, comment="快速预筛总次数"
    )
    precheck_triggered: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0, comment="预筛触发 AI 分析次数"
    )
    use_local_model: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="使用本地模型进行预筛"
    )
    local_model_klines: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, comment="本地模型分析的 K 线数量"
    )
```

### 3.2 AIBacktestTrade 模型

```python
# backend/app/models/ai_backtest_trade.py

class AIBacktestTrade(Base):
    __tablename__ = "ai_backtest_trades"

    # ... 现有字段保持不变 ...

    ai_window_start: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="AI 分析时 K 线窗口起始索引"
    )
    ai_window_end: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="AI 分析时 K 线窗口结束索引"
    )
    trigger_reason: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="触发 AI 分析的原因（预筛命中规则）"
    )
```

---

## 4. Schema 变更

### 4.1 AIBacktestCreate 输入 Schema

```python
# backend/app/schemas/ai_backtest.py

class AIBacktestCreate(BaseModel):
    """创建 AI 回测请求。"""

    strategy_id: uuid.UUID = Field(..., description="策略 ID")
    symbol: str = Field(..., description="交易对")
    timeframe: str = Field(..., description="K 线周期")
    start_time: datetime = Field(..., description="开始时间")
    mode: str = Field("kline_count", description="回测模式")
    kline_count: Optional[int] = Field(None, description="K 线数量")
    time_span_value: Optional[int] = Field(None, description="时间跨度值")
    time_span_unit: Optional[str] = Field(None, description="时间跨度单位")
    initial_capital: float = Field(10000, description="初始资金")
    fee_rate: float = Field(0.001, description="手续费率")
    use_ai: bool = Field(True, description="使用 AI 分析")
    prerequisites: Optional[Dict[str, Any]] = Field(None, description="策略前提规则")

    # 新增：本地模型预筛配置
    use_local_model: bool = Field(
        False, description="使用本地模型进行预筛（替代规则引擎预筛）"
    )
    local_model_klines: int = Field(
        10, ge=5, le=50, description="本地模型分析的 K 线数量（5-50）"
    )

    # 新增：多策略回测（可选，指定后会对每个策略分别回测）
    strategy_ids: Optional[List[uuid.UUID]] = Field(
        None, description="多个策略 ID（多策略分别回测时使用）"
    )
```

### 4.2 AIBacktestResponse 响应 Schema

```python
class AIBacktestResponse(BaseModel):
    # ... 现有字段 ...

    # 新增字段
    parent_backtest_id: Optional[uuid.UUID] = None
    strategy_ids: Optional[List[uuid.UUID]] = None
    ai_call_count: Optional[int] = None
    precheck_total: Optional[int] = None
    precheck_triggered: Optional[int] = None
    use_local_model: bool = False
    local_model_klines: int = 10
```

### 4.3 新增 Schema：MergeOptimizeRequest

```python
class MergeOptimizeRequest(BaseModel):
    """多策略融合优化请求。"""

    backtest_ids: List[uuid.UUID] = Field(
        ..., min_length=2, max_length=5,
        description="需要融合的回测 ID 列表（2-5 个）",
    )
    new_strategy_name: Optional[str] = Field(
        None, max_length=100,
        description="新策略名称（不指定则自动生成）",
    )
```

---

## 5. 核心逻辑变更

### 5.1 AIMarketAnalyzer - 新增 `quick_precheck()` AI粗略预筛

```python
# backend/app/utils/ai_market_analyzer.py

# 新增常量
PRECHECK_MAX_KLINES = 50     # 预筛最大 K 线数
PRECHECK_DEFAULT_KLINES = 10 # 预筛默认 K 线数

# 新增 Prompt
AI_QUICK_PRECHECK_PROMPT = """你是一个技术分析预筛助手。请快速分析最近K线，判断是否满足策略入场条件。

## 策略入场规则
{entry_rules}

## 最近 {kline_count} 根K线
{recent_klines}

## 技术指标摘要
{indicators_summary}

请判断：最近K线是否出现了符合策略入场规则条件的信号？
注意：只做粗略判断，不需要详细分析。

仅输出 JSON 格式：
{{"should_analyze": true/false, "reason": "判断理由（一句话）"}}

注意：
- 只输出JSON，不要输出其他文字
- 有明确的入场信号才返回true，模糊信号返回false
- 宁可漏过，不可误判（控制false positive）
"""


class AIMarketAnalyzer:
    # ... 现有方法 ...

    async def quick_precheck(
        self,
        kline_window: List[Dict],
        strategy_rules: Dict[str, Any],
        symbol: str,
        timeframe: str,
    ) -> bool:
        """AI 粗略预筛：使用主 AI Provider 分析少量 K 线，判断是否满足策略入场条件。

        Args:
            kline_window: K 线窗口数据（可配置，默认 10 根，范围 5-50）
            strategy_rules: 策略规则

        Returns:
            True = 可能满足条件，触发第二级 AI 深度分析
            False = 不满足，跳过
        """
        kline_count = len(kline_window)
        recent_klines_lines = []
        for i, k in enumerate(kline_window):
            recent_klines_lines.append(
                f"  [{i+1}] O{k['open']:.2f} H{k['high']:.2f} "
                f"L{k['low']:.2f} C{k['close']:.2f} V{k.get('volume', 0):.0f}"
            )
        recent_klines = "\n".join(recent_klines_lines)

        closes = [k["close"] for k in kline_window]
        highs = [k["high"] for k in kline_window]
        lows = [k["low"] for k in kline_window]
        volumes = [k.get("volume", 0) for k in kline_window]
        indicators = (
            f"价格区间: {min(lows):.2f} - {max(highs):.2f}\n"
            f"涨跌幅: {((closes[-1] - closes[0]) / closes[0] * 100):.2f}%\n"
            f"平均成交量: {sum(volumes) / len(volumes):.0f}"
        )

        entry_rules = strategy_rules.get("entry_rules", [])
        entry_rules_str = json.dumps(entry_rules, ensure_ascii=False, indent=2)

        prompt = AI_QUICK_PRECHECK_PROMPT.format(
            entry_rules=entry_rules_str,
            kline_count=kline_count,
            recent_klines=recent_klines,
            indicators_summary=indicators,
        )

        try:
            result = await self._call_llm(prompt, temperature=0.05, max_tokens=200)
            return self._parse_precheck_result(result)
        except Exception as e:
            logger.warning(f"AI quick precheck failed: {e}")
            # 失败时保守处理：返回 True，让第二级 AI 分析
            return True

    def _parse_precheck_result(self, raw: str) -> bool:
        """解析预筛结果。"""
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                result = json.loads(raw[start:end + 1])
                return bool(result.get("should_analyze", False))
            return False
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse precheck result: {e}")
            return False
```

### 5.2 新增：LocalModelPrechecker 本地模型预筛器

```python
# backend/app/utils/local_model_prechecker.py

"""本地模型预筛器：使用 Ollama 分析少量 K 线是否满足策略入场条件。"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LOCAL_MODEL_PRECHECK_PROMPT = """你是一个技术分析预筛助手。请分析最近的K线，判断是否值得进一步使用大模型进行深度分析。

## 策略入场规则
{entry_rules}

## 最近 {kline_count} 根K线
{recent_klines}

## 技术指标
{indicators}

请判断：最近K线是否出现了符合策略入场规则条件的信号？
仅输出 JSON 格式，不要输出其他文字：
{{"should_analyze": true/false, "reason": "判断理由（一句话）"}}

注意：
- 有明确的入场信号才返回 true，模糊信号返回 false
- 宁可漏过，不可误判（控制 false positive）
- 如果策略规则要求特定条件（如MA金叉、RSI超卖等），请严格检查
"""


class LocalModelPrechecker:
    """本地模型预筛器。

    调用 Ollama 本地模型分析少量 K 线，判断是否满足策略入场条件。
    如果满足，再触发大模型深度分析，否则跳过以节省 Token。
    """

    def __init__(self, session_maker=None):
        self._session_maker = session_maker

    async def _get_provider(self):
        """获取本地 Ollama provider。"""
        from app.services.provider_factory import ProviderFactory
        from sqlalchemy.ext.asyncio import AsyncSession

        if self._session_maker:
            async with self._session_maker() as db:
                return await ProviderFactory.get_provider_by_type(db, "ollama")
        # 兜底：从 ProviderFactory 获取
        raise RuntimeError("No session maker available for LocalModelPrechecker")

    async def precheck(
        self,
        kline_window: List[Dict[str, Any]],
        strategy_rules: Dict[str, Any],
        symbol: str,
        timeframe: str,
    ) -> bool:
        """本地模型预筛。

        Args:
            kline_window: K 线窗口数据（可配置数量，默认 10 根，范围 5-50）
            strategy_rules: 策略规则（含入场规则）
            symbol: 交易对
            timeframe: K 线周期

        Returns:
            True = 满足条件，触发 AI 深度分析
            False = 不满足，跳过
        """
        # 构建 K 线摘要
        kline_count = len(kline_window)
        recent_klines_lines = []
        for i, k in enumerate(kline_window):
            recent_klines_lines.append(
                f"  [{i+1}] 开{k['open']:.2f} 高{k['high']:.2f} "
                f"低{k['low']:.2f} 收{k['close']:.2f} 量{k.get('volume', 0):.0f}"
            )
        recent_klines = "\n".join(recent_klines_lines)

        # 技术指标
        closes = [k["close"] for k in kline_window]
        highs = [k["high"] for k in kline_window]
        lows = [k["low"] for k in kline_window]
        volumes = [k.get("volume", 0) for k in kline_window]
        indicators = (
            f"价格区间: {min(lows):.2f} - {max(highs):.2f}\n"
            f"涨跌幅: {((closes[-1] - closes[0]) / closes[0] * 100):.2f}%\n"
            f"平均成交量: {sum(volumes) / len(volumes):.0f}"
        )

        # 提取入场规则
        entry_rules = strategy_rules.get("entry_rules", [])
        entry_rules_str = json.dumps(entry_rules, ensure_ascii=False, indent=2)

        prompt = LOCAL_MODEL_PRECHECK_PROMPT.format(
            entry_rules=entry_rules_str,
            kline_count=kline_count,
            recent_klines=recent_klines,
            indicators=indicators,
        )

        # 调用本地模型
        try:
            provider = await self._get_provider()
            # 使用低 temperature 保证判断一致性
            result = await provider.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.05,
                max_tokens=200,
            )
            return self._parse_result(result)
        except Exception as e:
            logger.warning(f"Local model precheck failed: {e}")
            # 失败时保守处理：返回 True，让主 AI 分析
            return True

    def _parse_result(self, raw: str) -> bool:
        """解析本地模型返回结果。"""
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                result = json.loads(raw[start:end + 1])
                return bool(result.get("should_analyze", False))
            return False
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse local model result: {e}")
            return False
```

### 5.3 AIMarketAnalyzer - 新增 `analyze_with_window()`

```python
# backend/app/utils/ai_market_analyzer.py

# 新增常量
AI_ANALYSIS_MAX_WINDOW = 300  # AI 分析最大 K 线窗口
AI_ANALYSIS_WINDOW_PROMPT = """你是一个专业的加密货币交易AI助手，正在辅助用户进行策略回测。

当前回测信息：
- 策略类型：{strategy_category}
- 交易对：{symbol}
- 时间周期：{timeframe}
- 当前已推进：第 {current_kline_index} 根 / 共 {total_klines} 根
- K线窗口：最近 {window_size} 根（从索引 {window_start} 到 {window_end}）

## K线窗口摘要
{window_summary}

## 最近K线（最新5根）
{recent_klines_detail}

## 技术指标
{indicators_summary}

{position_status}

## 策略规则摘要
{strategy_rules}

请分析以上K线窗口中的市场状态，特别是最新K线的信号，并给出交易决策。

输出格式（只输出JSON）：
{{
  "market_analysis": {{
    "trend": "bullish/bearish/neutral",
    "strength": 3,
    "summary": "基于窗口数据的简要分析"
  }},
  "decision": "open_long/open_short/close_long/close_short/hold",
  "trade_plan": {{
    "action": "同上",
    "reason": "理由",
    "confidence": 4,
    "entry_price": 0,
    "quantity": 0,
    "stop_loss": 0,
    "take_profit": 0,
    "position_size_pct": 0.3
  }}
}}

注意：
- 只输出JSON，不要输出其他文字
- 如果无操作，decision为"hold"，trade_plan留空
- 如果开仓，必须提供合理的止盈止损价
- 基于K线窗口数据做出判断，而非仅凭最新一根K线
"""


class AIMarketAnalyzer:
    # ... 现有方法 ...

    async def analyze_with_window(
        self,
        symbol: str,
        timeframe: str,
        kline_window: List[Dict],
        indicators: Dict[str, Any],
        position: Optional[Dict[str, Any]],
        strategy_rules: Dict[str, Any],
        account_status: Dict[str, Any],
        current_kline_index: int,
        total_klines: int,
    ) -> Dict[str, Any]:
        """AI 深度分析（限制 K 线窗口最多 300 根）。

        Args:
            kline_window: K 线窗口数据，由调用方截取（最多 300 根）
        """
        # 构建 K 线窗口摘要
        window_size = len(kline_window)
        window_start = current_kline_index - window_size + 1
        window_end = current_kline_index

        # K 线窗口摘要（统计信息，非全量数据）
        closes = [k["close"] for k in kline_window]
        highs = [k["high"] for k in kline_window]
        lows = [k["low"] for k in kline_window]
        volumes = [k.get("volume", 0) for k in kline_window]

        window_summary = (
            f"价格区间: {min(lows):.2f} - {max(highs):.2f}\n"
            f"开盘: {kline_window[0]['open']:.2f}, 收盘: {kline_window[-1]['close']:.2f}\n"
            f"涨跌幅: {((kline_window[-1]['close'] - kline_window[0]['open']) / kline_window[0]['open'] * 100):.2f}%\n"
            f"平均成交量: {sum(volumes) / len(volumes):.0f}\n"
            f"最高成交量: {max(volumes):.0f}"
        )

        # 最近 5 根 K 线详细数据
        recent_5 = kline_window[-5:]
        recent_klines_detail = "\n".join([
            f"  [{i+1}] 开{k['open']:.2f} 高{k['high']:.2f} 低{k['low']:.2f} "
            f"收{k['close']:.2f} 量{k.get('volume', 0):.0f}"
            for i, k in enumerate(recent_5)
        ])

        # 构建 Prompt
        position_status = "无持仓"
        if position:
            position_status = (
                f"当前持仓：方向={position['direction']}, "
                f"开仓价={position['entry_price']}, "
                f"浮动盈亏={position.get('unrealized_pnl', 0)}"
            )

        strategy_category = strategy_rules.get("category", "自定义")
        strategy_summary = (
            f"入场规则: {strategy_rules.get('entry_rules', [])}\n"
            f"出场规则: {strategy_rules.get('exit_rules', [])}"
        )

        indicators_summary = (
            f"MA5={indicators.get('ma5', 'N/A'):.2f}, "
            f"MA10={indicators.get('ma10', 'N/A'):.2f}, "
            f"EMA20={indicators.get('ema20', 'N/A'):.2f}, "
            f"RSI(14)={indicators.get('rsi_14', 'N/A'):.1f}"
        )

        prompt = AI_ANALYSIS_WINDOW_PROMPT.format(
            strategy_category=strategy_category,
            symbol=symbol,
            timeframe=timeframe,
            current_kline_index=current_kline_index,
            total_klines=total_klines,
            window_size=window_size,
            window_start=window_start,
            window_end=window_end,
            window_summary=window_summary,
            recent_klines_detail=recent_klines_detail,
            indicators_summary=indicators_summary,
            position_status=position_status,
            strategy_rules=strategy_summary,
        )

        # 调用 LLM
        result = await self._call_llm(prompt)
        return self._parse_result(result)
```

### 5.3 AIBacktestService - 新增 `merge_optimize()`

```python
# backend/app/services/ai_backtest_service.py

class AIBacktestService:
    # ... 现有方法 ...

    async def merge_optimize(
        self, user_id: uuid.UUID, backtest_ids: List[uuid.UUID], new_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """多策略融合优化：综合分析多个回测结果，生成融合策略。

        流程：
        1. 验证所有回测均为当前用户所有且已完成
        2. 读取每个回测的原始策略规则 + 回测结果摘要
        3. 读取已有 AI 分析结果（如有）
        4. 构建融合 Prompt 调用 LLM
        5. 创建新策略
        6. 记录融合关系（parent_backtest_id, strategy_ids）
        """
        if len(backtest_ids) < 2 or len(backtest_ids) > 5:
            raise BadRequestException(message="需要 2-5 个回测进行融合")

        # 1. 验证所有权和状态
        strategies = []
        backtests = []
        analyses = []

        for bt_id in backtest_ids:
            backtest = await self._verify_ownership(bt_id, user_id)
            if backtest.status != "completed":
                raise BadRequestException(
                    message=f"回测 {bt_id} 状态为 {backtest.status}，需要已完成"
                )
            # 读取原始策略
            strategy_result = await self.db.execute(
                select(Strategy).where(Strategy.id == backtest.strategy_id)
            )
            strategy = strategy_result.scalar_one_or_none()
            if not strategy:
                raise NotFoundException(message=f"回测 {bt_id} 的策略不存在")

            strategies.append(strategy)
            backtests.append(backtest)
            analyses.append(
                (backtest.result_summary or {}).get("ai_analysis", {})
            )

        # 2. 构建融合 Prompt
        prompt = self._build_merge_optimize_prompt(strategies, backtests, analyses)

        # 3. 调用 LLM
        provider = await ProviderFactory.get_active_provider(self.db)
        raw_result = await provider.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        merged_rules = self._parse_optimize_result(raw_result)

        # 4. 计算版本号
        base_name = new_name or "多策略融合版"
        version = self._get_next_version(base_name, user_id)

        # 5. 创建新策略
        new_strategy = Strategy(
            user_id=user_id,
            name=f"{base_name} v{version}",
            category=merged_rules.get("category", "merged"),
            rules=merged_rules,
            description=f"AI 融合 {len(backtest_ids)} 个策略自动生成",
            extra={
                "source_backtest_ids": [str(b.id) for b in backtests],
                "original_strategy_ids": [str(s.id) for s in strategies],
                "merged_by_ai": True,
                "merge_type": "multi_strategy",
            },
        )
        self.db.add(new_strategy)
        await self.db.flush()

        return {
            "id": new_strategy.id,
            "name": new_strategy.name,
            "rules": merged_rules,
            "source_backtest_ids": [str(b.id) for b in backtests],
            "source_strategy_names": [s.name for s in strategies],
        }

    def _build_merge_optimize_prompt(
        self,
        strategies: List[Strategy],
        backtests: List[AIBacktest],
        analyses: List[Dict[str, Any]],
    ) -> str:
        """构建多策略融合优化 Prompt。"""
        parts = ["你是一个专业的量化交易策略融合专家。请综合以下多个策略的回测结果，融合生成一个全新的最优策略。\n"]

        for i, (strategy, backtest, analysis) in enumerate(zip(strategies, backtests, analyses)):
            summary = backtest.result_summary or {}
            parts.append(f"## 策略 {i+1}：{strategy.name}")
            parts.append(f"类型：{strategy.category}")
            parts.append(f"规则：{json.dumps(strategy.rules, ensure_ascii=False, indent=2)}")
            parts.append(f"回测结果：{json.dumps(summary, ensure_ascii=False, indent=2)}")
            if analysis:
                parts.append(f"AI 分析：{json.dumps(analysis, ensure_ascii=False, indent=2)}")
            parts.append("")

        parts.append("""## 融合要求
1. 取各策略的优势，摒弃劣势
2. 融合后的策略必须逻辑自洽，规则之间不冲突
3. 必须包含三条默认前提规则（单仓、止损、严格执规）
4. 输出完整的策略规则（入场、出场、仓位管理、风控）

输出 JSON 格式：
{
  "category": "merged",
  "entry_rules": [...],
  "exit_rules": [...],
  "position_sizing": {...},
  "risk_control": {...},
  "prerequisites": {...},
  "fusion_notes": "融合说明（2-3句话，说明取了哪些策略的什么优势）"
}

注意：只输出 JSON，不要输出其他文字。""")

        return "\n".join(parts)
```

### 5.5 AIBacktestContext - 新增字段

```python
# backend/app/tasks/ai_backtest_tasks.py

class AIBacktestContext:
    def __init__(self, backtest_id: str, config: dict):
        # ... 现有字段 ...

        # 新增字段
        self.ai_analysis_paused: bool = False
        self.last_analysis_kline_index: int = 0
        self.precheck_total: int = 0
        self.precheck_triggered: int = 0
        self.last_ai_kline_window: Optional[Tuple[int, int]] = None  # (start, end)
        self.last_trigger_reason: Optional[str] = None

        # 本地模型预筛配置
        self.use_local_model: bool = config.get("use_local_model", False)
        self.local_model_klines: int = config.get("local_model_klines", 10)
```

### 5.6 主循环重写

```python
# backend/app/tasks/ai_backtest_tasks.py

async def _run_backtest_async(backtest_id: str):
    """异步执行回测主逻辑（优化版）。"""
    # ... 加载配置、预热数据、拉取回测数据（不变）...

    # 初始化本地模型预筛器
    local_prechecker = None
    if ctx.use_local_model:
        try:
            from app.utils.local_model_prechecker import LocalModelPrechecker
            local_prechecker = LocalModelPrechecker(session_maker=local_session_maker)
        except Exception as e:
            logger.warning(f"Failed to init LocalModelPrechecker: {e}, fallback to main AI precheck")
            ctx.use_local_model = False

    for idx, kline in enumerate(backtest_klines):
        ctx.current_kline_index = idx + 1

        # === 停止信号检查 ===
        if _check_stop_signal(backtest_id):
            return

        kline_data = ctx.all_klines[:ctx.preheat_count + idx + 1]
        indicators = _calculate_indicators(kline_data)

        # === 核心优化：持仓免分析 + 两级 AI 过滤 ===
        ai_result = None
        should_analyze = ctx.use_ai_real

        if should_analyze:
            if ctx.current_position is not None:
                # 有持仓：跳过 AI 分析
                should_analyze = False
                ctx.ai_analysis_paused = True
            else:
                # 无持仓：两级 AI 过滤
                # 第一级：AI 粗略预筛（主 AI 或 本地模型）
                if ctx.use_local_model and local_prechecker:
                    # 模式 B：本地模型预筛
                    local_window = kline_data[-ctx.local_model_klines:]
                    precheck_result = await local_prechecker.precheck(
                        kline_window=local_window,
                        strategy_rules=ctx.strategy_rules,
                        symbol=ctx.symbol,
                        timeframe=ctx.timeframe,
                    )
                    ctx.precheck_total += 1
                    if precheck_result:
                        ctx.precheck_triggered += 1
                        should_analyze = True
                        ctx.last_trigger_reason = "local_model"
                    else:
                        should_analyze = False
                        logger.debug(f"本地模型预筛未通过 at kline {idx+1}")
                else:
                    # 模式 A（默认）：主 AI 粗略预筛
                    quick_window = kline_data[-ctx.local_model_klines:]
                    precheck_result = await analyzer.quick_precheck(
                        kline_window=quick_window,
                        strategy_rules=ctx.strategy_rules,
                        symbol=ctx.symbol,
                        timeframe=ctx.timeframe,
                    )
                    ctx.precheck_total += 1
                    if precheck_result:
                        ctx.precheck_triggered += 1
                        should_analyze = True
                        ctx.last_trigger_reason = "ai_precheck"
                    else:
                        should_analyze = False
                        logger.debug(f"AI 粗略预筛未通过 at kline {idx+1}")

                # 第二级：AI 深度分析（预筛通过时，最多 300 根）
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
                            account_status={...},
                            current_kline_index=idx + 1,
                            total_klines=ctx.total_klines,
                        )
                        ctx.ai_call_count += 1
                        ctx.ai_fail_count = 0
                    except Exception as e:
                        ctx.ai_fail_count += 1
                        logger.warning(f"AI 深度分析失败 at kline {idx+1}: {e}")
                        if ctx.ai_fail_count >= 3:
                            ctx.use_ai_real = False

        # 执行决策
        executor.execute(kline, ai_result, indicators)

        # === 持仓免分析恢复检查 ===
        if ctx.current_position is None and ctx.ai_analysis_paused:
            ctx.ai_analysis_paused = False
            logger.info(f"平仓完成，恢复 AI 分析 at kline {idx+1}")

        # 更新进度（每 10 根或最后 10 根）
        # ... 不变 ...
```

---

## 6. API 接口变更

### 6.1 新增：多策略融合优化

```python
# backend/app/api/v1/ai_backtest_routes.py

@router.post("/merge-optimize", summary="多策略融合优化")
async def merge_optimize_strategies(
    data: MergeOptimizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于多个回测结果融合生成新策略。

    请求体：
    {
        "backtest_ids": ["uuid1", "uuid2", "uuid3"],
        "new_strategy_name": "可选的新策略名称"
    }

    响应：
    {
        "id": "新策略ID",
        "name": "多策略融合版 v1",
        "rules": {...},
        "source_backtest_ids": ["uuid1", "uuid2", "uuid3"],
        "source_strategy_names": ["策略A", "策略B", "策略C"]
    }
    """
    service = AIBacktestService(db)
    result = await service.merge_optimize(
        current_user.id, data.backtest_ids, data.new_strategy_name
    )
    return ApiResponse(data=result)
```

### 6.2 创建回测接口扩展

`POST /strategies/ai-backtest` 接口新增支持 `strategy_ids` 字段：

- 当 `strategy_ids` 不为空时，表示为每个策略分别创建回测
- 返回多个回测 ID 列表
- 前端可分别跟踪每个回测的进度

---

## 7. 错误处理

| 错误场景 | 错误类型 | 处理方式 |
|----------|----------|----------|
| 回测状态非 completed | BadRequestException | 提示用户先等待回测完成 |
| 回测不属于当前用户 | NotFoundException | 返回 404 |
| 融合少于 2 个回测 | BadRequestException | 提示至少需要 2 个 |
| 融合多于 5 个回测 | BadRequestException | 提示最多 5 个 |
| AI 连续失败 3 次 | 降级处理 | 自动关闭 AI 分析，降级为非 AI 回测 |
| AI 粗略预筛异常 | 降级处理 | 失败时保守返回 True，让第二级 AI 分析 |
| 本地模型预筛异常 | 降级处理 | 失败时保守返回 True，让第二级 AI 分析 |
| 本地模型初始化失败 | 降级处理 | 自动降级为模式 A（主 AI 粗略预筛） |

---

## 8. 性能优化

### 8.1 指标计算优化

现有 `_calculate_indicators` 每次传入全部历史数据，计算量随 K 线数线性增长。优化为增量计算：

```python
# 全局缓存技术指标计算结果
_indicators_cache: Dict[str, Dict[str, Any]] = {}

def _calculate_indicators_cached(klines: List[Dict], cache_key: str) -> Dict[str, Any]:
    """带缓存的指标计算（仅重新计算最后部分）。"""
    # 如果缓存存在且数据长度一致，直接返回
    # 否则增量计算
```

### 8.2 SSE 推送优化

进度推送从每 10 根调整为每 20 根，减少 Redis 写入频率。

---

## 9. 测试要点

### 9.1 单元测试

| 测试项 | 说明 |
|--------|------|
| `quick_precheck` 预筛逻辑 | 测试 Prompt 构建和结果解析 |
| `analyze_with_window` 窗口截取 | 确认窗口大小不超过 300 |
| 持仓免分析 | 确认持仓期间不调用 AI |
| 平仓恢复 | 确认平仓后恢复 AI 分析 |
| 多策略融合 | 验证 Prompt 构建和结果解析 |
| 本地模型预筛 | 测试 Prompt 构建、结果解析、失败降级 |
| 预筛模式切换 | 验证 use_local_model 开关切换主 AI / 本地模型 |

### 9.2 集成测试

| 测试项 | 说明 |
|--------|------|
| 完整回测流程 | 100 根 K 线回测，确认 AI 调用次数显著减少 |
| 多策略融合 API | 创建 2 个回测 → 融合优化 → 确认新策略生成 |
| 并发控制 | 同一用户最多 3 个回测同时运行 |