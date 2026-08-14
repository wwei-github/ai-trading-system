"""AI 市场分析封装。"""

import json
import logging
from typing import Any, Dict, Optional

from app.services.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)

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
- 仓位管理参考策略规则中的position_sizing

⚠️ 严格执规要求：
- 你必须严格遵守以下策略规则，不可擅自偏离或创造新规则
- 入场信号必须符合策略的入场规则
- 出场信号必须符合策略的出场规则
- 仓位大小必须符合策略的仓位管理规则
"""


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
        )

        # 调用 LLM（异步方式，在 Celery 任务的 asyncio.run() 上下文中运行）
        try:
            result = await self._call_llm(prompt)
            return self._parse_result(result)
        except Exception as e:
            logger.error(f"AI analyze failed: {e}")
            raise

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM 获取分析结果。"""
        session_maker = await self._get_session_maker()
        async with session_maker() as db:
            provider = await ProviderFactory.get_active_provider(db)
            result = await provider.chat(prompt, temperature=0.1)
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