"""AI 市场分析封装。"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.services.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)

# ========== 原有 Prompt ==========

_MARKET_ANALYSIS_PROMPT = """你是一个专业的加密货币交易AI助手，正在辅助用户进行策略回测。

当前回测信息：
- 策略类型：{strategy_category}
- 交易对：{symbol}
- 时间周期：{timeframe}
- 当前已推进：第 {current_kline_index} 根 / 共 {total_klines} 根

当前市场状态：
- 最新K线：开 {open} 高 {high} 低 {low} 收 {close} 量 {volume}
- 技术指标：MA5={ma5} MA10={ma10} RSI={rsi}
- 关键支撑：{support_levels}
- 关键阻力：{resistance_levels}

{position_status}

策略规则摘要：
{strategy_rules}

请分析当前市场状态，并给出交易决策。

### 开仓要求：
- 入场信号必须严格符合策略的入场规则（entry_rules）
- 如果开仓，必须提供止损价（stop_loss）
- 止损价必须基于策略指定的止损方式（如 Pinbar 极值、ATR倍数、固定百分比等）
- 止盈价（take_profit）必须基于合理的盈亏比（至少 1.5R，建议 1.5R~2R）
- 仓位大小（position_size_pct）必须遵循策略的仓位管理规则
- 开仓理由（reason）必须说明哪个具体规则条件触发了信号

### 持仓管理：
- 有持仓时，基于策略的出场规则（exit_rules）判断是否平仓
- 平仓理由必须说明哪个具体规则条件触发了平仓

输出格式：按JSON格式输出，包含market_analysis、decision、trade_plan三个字段。
{{
  "market_analysis": {{
    "trend": "bullish/bearish/neutral",
    "strength": 3,
    "summary": "简要分析"
  }},
  "decision": "open_long/open_short/close_long/close_short/hold",
  "trade_plan": {{
    "action": "同上",
    "reason": "理由（必须说明触发的具体规则条件）",
    "confidence": 4,
    "entry_price": 0,
    "quantity": 0,
    "stop_loss": 0,
    "take_profit": 0,
    "position_size_pct": 0.3,
    "stop_loss_method": "止损方式说明",
    "risk_reward_ratio": 1.5
  }}
}}

注意：
- 只输出JSON，不要输出其他文字
- 如果无操作，decision为"hold"，trade_plan留空
- 如果开仓，必须提供合理的止盈止损价
- 仓位管理参考策略规则中的position_sizing
- 止损方式必须参考策略规则中的risk_control

⚠️ 严格执规要求：
- 你必须严格遵守以下策略规则，不可擅自偏离或创造新规则
- 入场信号必须符合策略的入场规则
- 出场信号必须符合策略的出场规则
- 仓位大小必须符合策略的仓位管理规则
- 止损方式必须符合策略的风控规则
"""

# ========== 08-AI回测K线分析优化 新增 Prompt ==========

# 快速预筛 Prompt
AI_QUICK_PRECHECK_PROMPT = """你是一个技术分析预筛助手。请快速分析最近K线，判断是否满足策略入场条件。

## 策略入场规则（可能包含多个策略的规则，每个策略独立判断）
{entry_rules}

## 最近 {kline_count} 根K线
{recent_klines}

## 当前最新价格
最新K线收盘价：{current_close:.2f}
最新K线最高价：{current_high:.2f}
最新K线最低价：{current_low:.2f}

## 技术指标摘要
{indicators_summary}

请判断：最近K线是否出现了符合策略入场规则条件的信号？

### 判断规则（重要）：
- 每个策略的入场规则**独立判断**，互不干扰
- 对于每个策略，逐一检查其入场规则是否满足当前K线条件
- **只要任意一个策略的入场条件满足**，就应返回 should_analyze=true
- 只做粗略判断，不需要详细分析

### 输出要求：
- reason 中必须**每个策略换一行**，逐一列出每个策略的判断结果，说明各自是否满足条件
- 格式示例：
  逐一检查所有策略：
  策略A：
       条件1:满足（均线金叉）
       条件2:不满足（RSI未超卖）
  策略B：
       条件1:满足（RSI未超卖）
       条件2:满足（价格突破前高）
  策略C：
       条件1:满足（价格突破前高）
       条件2:满足（RSI未超卖）
- 如果只有一个策略，换行说明该策略条件是否满足
- 格式示例：
  策略A：
       条件1:满足（均线金叉）
       条件2:不满足（RSI未超卖）

仅输出 JSON 格式：
{{"should_analyze": true/false, "reason": "判断理由（每个策略一行，逐一列出每个策略的判断结果）"}}

注意：
- 只输出JSON，不要输出其他文字
- 有明确的入场信号才返回true，模糊信号返回false
- 宁可漏过，不可误判（控制false positive）
"""

# 深度分析窗口 Prompt
AI_ANALYSIS_WINDOW_PROMPT = """你是一个专业的加密货币交易AI助手，正在辅助用户进行策略回测。

当前回测信息：
- 策略类型：{strategy_category}
- 交易对：{symbol}
- 时间周期：{timeframe}
- 当前已推进：第 {current_kline_index} 根 / 共 {total_klines} 根
- K线窗口：最近 {window_size} 根（从索引 {window_start} 到 {window_end}）
- 当前最新价格：{current_price}

## K线窗口摘要
{window_summary}

## 最近K线（最新5根）
{recent_klines_detail}

## 技术指标
{indicators_summary}

{position_status}

## 策略规则摘要
{strategy_rules}

## 仓位管理规则
{position_sizing_rules}

## 风控规则
{risk_control_rules}

## 策略前提规则（必须遵守）
{prerequisites_rules}

请分析以上K线窗口中的市场状态，特别是最新K线的信号，并给出交易决策。

### 多策略决策规则（重要）：
- 如果存在多个策略，**每个策略的入场条件必须独立判断**
- 对于每个策略，你必须：
  1. 逐一检查该策略的所有入场规则
  2. 明确说明该策略的条件是否满足
  3. 简要说明判断依据
- **只要任意一个策略的入场条件满足**，即可开仓
- 开仓理由中必须**逐一列出每个策略**的判断结果
- 通过 source_strategy 指定最终触发开仓的是哪个策略

### 开仓要求：
- 入场信号必须严格符合策略的入场规则（entry_rules）
- 如果开仓，必须提供止损价（stop_loss）
- 止损价必须基于策略指定的止损方式（如 Pinbar 极值、ATR倍数、固定百分比等）
- 止盈价（take_profit）必须基于合理的盈亏比（至少 1.5R，建议 1.5R~2R）
- 仓位大小（position_size_pct）必须遵循触发策略的仓位管理规则
- 开仓理由（reason）必须：
  1. **逐一说明每个策略**是否满足入场条件及判断依据
  2. **每个策略一行**，格式示例：
     逐一检查所有策略：
     策略A：满足（均线金叉）
     策略B：不满足（RSI未超卖）
  3. 说明触发开仓的具体策略和规则条件
  4. 总结为什么满足条件就可以开仓

### 持仓管理：
- 有持仓时，基于策略的出场规则（exit_rules）判断是否平仓
- 平仓理由必须说明哪个具体规则条件触发了平仓

输出格式（只输出JSON，不要输出其他文字）：
{{
  "market_analysis": {{
    "trend": "bullish/bearish/neutral",
    "strength": 3,
    "summary": "基于窗口数据的简要分析"
  }},
  "decision": "open_long/open_short/close_long/close_short/hold",
  "source_strategy": "触发开仓的策略名称（如只有一个策略则留空，多个策略时必填）",
  "trade_plan": {{
    "action": "同上",
    "reason": "理由（每个策略一行，逐一说明各策略是否满足条件及判断依据，然后说明触发开仓的具体策略和规则，总结为什么满足条件）",
    "confidence": 4,
    "entry_price": 0,
    "quantity": 0,
    "stop_loss": 0,
    "take_profit": 0,
    "position_size_pct": 0.3,
    "stop_loss_method": "止损方式说明",
    "risk_reward_ratio": 1.5
  }}
}}
"""

# 初始化分析 Prompt
INITIAL_ANALYSIS_PROMPT_TEMPLATE = """你是一个专业的加密货币市场分析师。
请分析最近 {count} 根K线，给出整体趋势判断、关键支撑位和压力位。

## 最近K线数据（{count}根，从旧到新）
{kline_summary}

## 技术指标摘要
{indicators_summary}

## 策略入场规则
{entry_rules}

请输出 JSON：
{{
  "trend": "bullish/bearish/neutral",
  "trend_summary": "趋势摘要（30字以内）",
  "key_levels": [
    {{"type": "support", "price": 0}},
    {{"type": "resistance", "price": 0}}
  ]
}}
"""

# 计算常量
PRECHECK_MAX_KLINES = 50
PRECHECK_DEFAULT_KLINES = 10
AI_ANALYSIS_MAX_WINDOW = 300


class AIMarketAnalyzer:
    """AI 市场分析器。"""

    def __init__(self, session_maker=None):
        """
        Args:
            session_maker: 异步 session maker（Celery 子进程中使用局部 session maker）
        """
        self._session_maker = session_maker

    async def _get_session_maker(self):
        """获取 session maker（优先使用外部传入的，否则创建全新的）。"""
        if self._session_maker:
            return self._session_maker
        from app.tasks.ai_backtest_tasks import _make_local_session_maker
        _, maker = await _make_local_session_maker()
        return maker

    async def analyze(
        self,
        symbol: str,
        timeframe: str,
        kline: Dict[str, Any],
        indicators: Dict[str, Any],
        position: Optional[Dict[str, Any]],
        strategy_rules: Dict[str, Any],
        account_status: Dict[str, Any],
        current_kline_index: int,
        total_klines: int,
        multi_strategy_rules: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        调用 AI 分析当前市场并给出决策。

        Returns:
            AI 分析结果字典，包含 market_analysis, decision, trade_plan
        """
        # 构建 Prompt
        position_status = "无持仓"
        if position:
            position_status = (
                f"当前持仓：方向={position['direction']}, "
                f"开仓价={position['entry_price']}, "
                f"浮动盈亏={position.get('unrealized_pnl', 0)}, "
                f"持仓K线数={position.get('holding_bars', 0)}, "
                f"止损={position.get('stop_loss', 'N/A')}, "
                f"止盈={position.get('take_profit', 'N/A')}"
            )

        strategy_category = strategy_rules.get("category", "自定义")
        strategy_summary = (
            f"入场规则: {strategy_rules.get('entry_rules', [])}\n"
            f"出场规则: {strategy_rules.get('exit_rules', [])}\n"
            f"仓位管理: {strategy_rules.get('position_sizing', {})}\n"
            f"风控: {strategy_rules.get('risk_control', {})}"
        )

        # 多策略参考规则
        multi_strategy_section = ""
        if multi_strategy_rules:
            parts = []
            for s in multi_strategy_rules:
                parts.append(
                    f"--- {s.get('name', '未知策略')} ---\n"
                    f"入场规则: {s.get('rules', {}).get('entry_rules', [])}\n"
                    f"出场规则: {s.get('rules', {}).get('exit_rules', [])}\n"
                    f"仓位管理: {s.get('rules', {}).get('position_sizing', {})}\n"
                    f"风控: {s.get('rules', {}).get('risk_control', {})}"
                )
            multi_strategy_section = "\n\n## 参考策略规则（每个策略独立判断，任一满足即可开仓）\n" + "\n\n".join(parts)

        prompt = _MARKET_ANALYSIS_PROMPT.format(
            strategy_category=strategy_category,
            symbol=symbol,
            timeframe=timeframe,
            current_kline_index=current_kline_index,
            total_klines=total_klines,
            open=kline.get("open", 0),
            high=kline.get("high", 0),
            low=kline.get("low", 0),
            close=kline.get("close", 0),
            volume=kline.get("volume", 0),
            ma5=indicators.get("ma5", "N/A"),
            ma10=indicators.get("ma10", "N/A"),
            rsi=indicators.get("rsi_14", "N/A"),
            support_levels=indicators.get("support", []),
            resistance_levels=indicators.get("resistance", []),
            position_status=position_status,
            strategy_rules=strategy_summary,
        ) + multi_strategy_section

        # 调用 LLM（异步方式，在 Celery 任务的 asyncio.run() 上下文中运行）
        try:
            result = await self._call_llm(prompt)
            return self._parse_result(result)
        except Exception as e:
            logger.error(f"AI analyze failed: {e}")
            raise

    async def _call_llm(
        self, prompt: str, temperature: float = 0.1, max_tokens: Optional[int] = None
    ) -> str:
        """调用 LLM 获取分析结果。

        Args:
            prompt: 提示词
            temperature: 温度参数（预筛使用更低温度，分析使用默认）
            max_tokens: 最大 token 数
        """
        session_maker = await self._get_session_maker()
        async with session_maker() as db:
            provider = await ProviderFactory.get_active_provider(db)
            kwargs = {
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            result = await provider.chat(**kwargs)
            return result

    def _parse_result(self, raw: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON 结果。"""
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                json_str = raw[start:end + 1]
                return json.loads(json_str)
            raise ValueError("No JSON found in response")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI result: {e}, raw={raw[:200]}")
            raise

    # ========== 08-AI回测K线分析优化 新增方法 ==========

    def _get_template_content(self, category: str) -> str:
        """根据分类获取 Prompt 模板（默认使用内置常量，后续 Batch 4 接入 DB）。

        Args:
            category: 模板分类（initial_analysis / backtest_precheck / deep_analysis）

        Returns:
            模板字符串
        """
        templates = {
            "initial_analysis": INITIAL_ANALYSIS_PROMPT_TEMPLATE,
            "backtest_precheck": AI_QUICK_PRECHECK_PROMPT,
            "deep_analysis": AI_ANALYSIS_WINDOW_PROMPT,
        }
        return templates.get(category, _MARKET_ANALYSIS_PROMPT)

    async def quick_precheck(
        self,
        kline_window: List[Dict[str, Any]],
        strategy_rules: Dict[str, Any],
        symbol: str,
        timeframe: str,
        multi_strategy_rules: List[Dict[str, Any]] = None,
        computed_indicators: Dict[str, Any] = None,
    ) -> Tuple[bool, str]:
        """AI 粗略预筛：使用主 AI Provider 分析少量 K 线，判断是否满足策略入场条件。

        Args:
            kline_window: K 线窗口数据（可配置，默认 10 根，范围 5-50）
            strategy_rules: 策略规则
            symbol: 交易对
            timeframe: K 线周期
            multi_strategy_rules: 多策略规则列表
            computed_indicators: 已计算的指标字典（来自 _calculate_indicators），用于补充指标摘要

        Returns:
            (passed, raw_response): 是否满足条件、原始 AI 响应文本
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
        ci = computed_indicators or {}
        indicators = (
            f"价格区间: {min(lows):.2f} - {max(highs):.2f}\n"
            f"涨跌幅: {((closes[-1] - closes[0]) / closes[0] * 100):.2f}%\n"
            f"平均成交量: {sum(volumes) / len(volumes):.0f}\n"
            f"EMA50: {ci.get('ema50', 'N/A')}\n"
            f"Stochastic%D: {ci.get('stoch_d', 'N/A')}\n"
            f"Stochastic%K: {ci.get('stoch_k', 'N/A')}"
        )

        entry_rules = strategy_rules.get("entry_rules", [])
        # 多策略参考规则（保留策略名称，让AI能逐一判断每个策略）
        if multi_strategy_rules:
            parts = []
            # 主策略
            main_name = strategy_rules.get("name", "主策略")
            parts.append(
                f"--- {main_name}（主策略） ---\n"
                f"入场规则: {json.dumps(entry_rules, ensure_ascii=False, indent=2)}"
            )
            # 其他策略
            for s in multi_strategy_rules:
                s_name = s.get("name", "未知策略")
                s_entry = s.get("rules", {}).get("entry_rules", [])
                parts.append(
                    f"--- {s_name} ---\n"
                    f"入场规则: {json.dumps(s_entry, ensure_ascii=False, indent=2)}"
                )
            entry_rules_str = "\n\n".join(parts)
        else:
            entry_rules_str = json.dumps(entry_rules, ensure_ascii=False, indent=2)

        template = self._get_template_content("backtest_precheck")
        prompt = template.format(
            entry_rules=entry_rules_str,
            kline_count=kline_count,
            recent_klines=recent_klines,
            indicators_summary=indicators,
            current_close=closes[-1],
            current_high=highs[-1],
            current_low=lows[-1],
        )

        try:
            result = await self._call_llm(prompt, temperature=0.05, max_tokens=200)
            return self._parse_precheck_result(result), result
        except Exception as e:
            logger.warning(f"AI quick precheck failed: {e}")
            # 失败时保守处理：返回 True，让第二级 AI 分析
            return True, f"快速预筛执行失败: {e}"

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

    async def analyze_with_window(
        self,
        symbol: str,
        timeframe: str,
        kline_window: List[Dict[str, Any]],
        indicators: Dict[str, Any],
        position: Optional[Dict[str, Any]],
        strategy_rules: Dict[str, Any],
        account_status: Dict[str, Any],
        current_kline_index: int,
        total_klines: int,
        multi_strategy_rules: List[Dict[str, Any]] = None,
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

        # 多策略参考规则（深度分析）
        multi_strategy_section = ""
        if multi_strategy_rules:
            parts = []
            for s in multi_strategy_rules:
                parts.append(
                    f"--- {s.get('name', '未知策略')} ---\n"
                    f"入场规则: {s.get('rules', {}).get('entry_rules', [])}\n"
                    f"出场规则: {s.get('rules', {}).get('exit_rules', [])}\n"
                    f"仓位管理: {s.get('rules', {}).get('position_sizing', {})}\n"
                    f"风控: {s.get('rules', {}).get('risk_control', {})}"
                )
            multi_strategy_section = "\n\n## 参考策略规则（每个策略独立判断，任一满足即可开仓）\n" + "\n\n".join(parts)

        # 仓位管理、风控、前提规则
        position_sizing_rules = json.dumps(strategy_rules.get("position_sizing", {}), ensure_ascii=False, indent=2)
        risk_control_rules = json.dumps(strategy_rules.get("risk_control", {}), ensure_ascii=False, indent=2)
        prerequisites_rules = json.dumps(strategy_rules.get("prerequisites", {}), ensure_ascii=False, indent=2)

        indicators_summary = (
            f"MA5={indicators.get('ma5', 'N/A')}, "
            f"MA10={indicators.get('ma10', 'N/A')}, "
            f"EMA20={indicators.get('ema20', 'N/A')}, "
            f"EMA50={indicators.get('ema50', 'N/A')}, "
            f"RSI(14)={indicators.get('rsi_14', 'N/A')}, "
            f"Stochastic%K={indicators.get('stoch_k', 'N/A')}, "
            f"Stochastic%D={indicators.get('stoch_d', 'N/A')}"
        )
        # 格式化数值
        indicators_summary = self._format_indicator_value(indicators_summary, indicators)

        template = self._get_template_content("deep_analysis")
        prompt = template.format(
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
            position_sizing_rules=position_sizing_rules,
            risk_control_rules=risk_control_rules,
            prerequisites_rules=prerequisites_rules,
            current_price=closes[-1],
        ) + multi_strategy_section

        # 调用 LLM
        result = await self._call_llm(prompt)
        return self._parse_result(result)

    def _format_indicator_value(self, summary: str, indicators: Dict[str, Any]) -> str:
        """格式化指标数值，确保 N/A 正确处理。"""
        ma5 = indicators.get("ma5", "N/A")
        ma10 = indicators.get("ma10", "N/A")
        ema20 = indicators.get("ema20", "N/A")
        ema50 = indicators.get("ema50", "N/A")
        rsi = indicators.get("rsi_14", "N/A")
        stoch_k = indicators.get("stoch_k", "N/A")
        stoch_d = indicators.get("stoch_d", "N/A")
        ma5_str = f"{ma5:.2f}" if isinstance(ma5, (int, float)) else str(ma5)
        ma10_str = f"{ma10:.2f}" if isinstance(ma10, (int, float)) else str(ma10)
        ema20_str = f"{ema20:.2f}" if isinstance(ema20, (int, float)) else str(ema20)
        ema50_str = f"{ema50:.2f}" if isinstance(ema50, (int, float)) else str(ema50)
        rsi_str = f"{rsi:.1f}" if isinstance(rsi, (int, float)) else str(rsi)
        stoch_k_str = f"{stoch_k:.1f}" if isinstance(stoch_k, (int, float)) else str(stoch_k)
        stoch_d_str = f"{stoch_d:.1f}" if isinstance(stoch_d, (int, float)) else str(stoch_d)
        return (
            f"MA5={ma5_str}, MA10={ma10_str}, "
            f"EMA20={ema20_str}, EMA50={ema50_str}, "
            f"RSI(14)={rsi_str}, "
            f"Stochastic%K={stoch_k_str}, Stochastic%D={stoch_d_str}"
        )

    async def analyze_initial(
        self,
        kline_window: List[Dict[str, Any]],
        strategy_rules: Dict[str, Any],
        symbol: str,
        timeframe: str,
        multi_strategy_rules: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """初始化 300 根 K 线分析，提取趋势和关键位。

        Args:
            kline_window: K 线窗口数据（预热 300 根）
            strategy_rules: 策略规则
            symbol: 交易对
            timeframe: K 线周期

        Returns:
            {
                "trend": "bullish/bearish/neutral",
                "trend_summary": "趋势摘要",
                "key_levels": [{"type": "support", "price": 0}, ...]
            }
        """
        count = len(kline_window)

        # K 线摘要（采样显示，避免超出 token 限制）
        step = max(1, count // 50)  # 采样约 50 根
        sampled = kline_window[::step]
        kline_lines = []
        for k in sampled:
            kline_lines.append(
                f"O{k['open']:.2f} H{k['high']:.2f} "
                f"L{k['low']:.2f} C{k['close']:.2f} V{k.get('volume', 0):.0f}"
            )
        kline_summary = "\n".join(kline_lines)

        # 指标摘要
        closes = [k["close"] for k in kline_window]
        highs = [k["high"] for k in kline_window]
        lows = [k["low"] for k in kline_window]
        volumes = [k.get("volume", 0) for k in kline_window]
        indicators_summary = (
            f"价格区间: {min(lows):.2f} - {max(highs):.2f}\n"
            f"开盘: {kline_window[0]['open']:.2f}, 收盘: {kline_window[-1]['close']:.2f}\n"
            f"涨跌幅: {((kline_window[-1]['close'] - kline_window[0]['open']) / kline_window[0]['open'] * 100):.2f}%\n"
            f"平均成交量: {sum(volumes) / len(volumes):.0f}\n"
            f"K线数量: {count}"
        )

        entry_rules = strategy_rules.get("entry_rules", [])
        # 多策略入场规则合并
        if multi_strategy_rules:
            all_entry_rules = list(entry_rules)
            for s in multi_strategy_rules:
                s_entry = s.get("rules", {}).get("entry_rules", [])
                all_entry_rules.extend(s_entry)
            entry_rules = all_entry_rules

        template = self._get_template_content("initial_analysis")
        prompt = template.format(
            count=count,
            kline_summary=kline_summary,
            indicators_summary=indicators_summary,
            entry_rules=json.dumps(entry_rules, ensure_ascii=False),
        )

        try:
            result = await self._call_llm(prompt, temperature=0.2, max_tokens=600)
            return self._parse_initial_result(result)
        except Exception as e:
            logger.warning(f"Initial AI analysis failed: {e}")
            # 失败时返回空结构
            return {
                "trend": "neutral",
                "trend_summary": "AI 分析失败",
                "key_levels": [],
            }

    def _parse_initial_result(self, raw: str) -> Dict[str, Any]:
        """解析初始化分析结果。"""
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                result = json.loads(raw[start:end + 1])
                return {
                    "trend": result.get("trend", "neutral"),
                    "trend_summary": result.get("trend_summary", ""),
                    "key_levels": result.get("key_levels", []),
                }
            return {"trend": "neutral", "trend_summary": "", "key_levels": []}
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse initial result: {e}")
            return {"trend": "neutral", "trend_summary": "", "key_levels": []}