"""本地模型预筛器：使用 Ollama 分析少量 K 线是否满足策略入场条件。"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.services.provider_factory import ProviderFactory

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
    ) -> Tuple[bool, str]:
        """本地模型预筛。

        Args:
            kline_window: K 线窗口数据（可配置数量，默认 10 根，范围 5-50）
            strategy_rules: 策略规则（含入场规则）
            symbol: 交易对
            timeframe: K 线周期

        Returns:
            (passed, raw_response): 是否满足条件、原始 AI 响应文本
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
            return self._parse_result(result), result
        except Exception as e:
            logger.warning(f"Local model precheck failed: {e}")
            # 失败时保守处理：返回 True，让主 AI 分析
            return True, f"本地模型预筛执行失败: {e}"

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