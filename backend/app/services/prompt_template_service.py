"""Prompt 模板服务层。"""

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
)

logger = logging.getLogger(__name__)

# ========== 默认 Prompt 模板配置 ==========
DEFAULT_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "initial_analysis": [
        {
            "name": "默认预热分析模板",
            "content": """你是一个专业的加密货币技术分析师。请基于给定的 K 线数据窗口，分析市场状态。

## 分析要求
1. 判断当前趋势方向（bullish / bearish / neutral）
2. 评估趋势强度（1-5 分）
3. 识别关键支撑位和阻力位（最多 3 组）
4. 提供简洁的分析摘要

## 策略规则
{strategy_rules}

## 当前窗口数据
{symbol} {timeframe}
K 线数量: {kline_count}
最近 K 线数据: {kline_data}

## 输出格式（JSON）
{{
    "trend": "bullish | bearish | neutral",
    "strength": 1-5,
    "summary": "分析摘要",
    "key_levels": [
        {{"type": "support", "price": 数字}},
        {{"type": "resistance", "price": 数字}}
    ]
}}""",
        },
        {
            "name": "详细预热分析模板",
            "content": """你是一个专业的技术分析师，请对以下 K 线数据进行全面的初始分析。

## 分析维度
1. **趋势方向**：基于 MA5/MA10/EMA20/EMA50 判断
2. **趋势强度**：基于趋势持续性和波动率
3. **关键位**：识别近期价格行为中的支撑和阻力
4. **市场结构**：分析高点和低点关系

## 数据
{symbol} {timeframe}
K 线数据: {kline_data}

## 策略规则
{strategy_rules}

## 输出格式
{{
    "trend": "bullish | bearish | neutral",
    "strength": 1-5,
    "summary": "分析摘要",
    "key_levels": [
        {{"type": "support", "price": 数字}},
        {{"type": "resistance", "price": 数字}}
    ]
}}""",
        },
    ],
    "backtest_precheck": [
        {
            "name": "默认快速预筛模板",
            "content": """你是一个交易策略过滤器。请快速判断当前 K 线是否值得触发深度分析。

## 策略规则
{strategy_rules}

## 当前窗口
{symbol} {timeframe}
K 线数据: {kline_data}

## 判断标准
1. 当前价格是否接近策略入场条件
2. 是否有明显的趋势信号
3. 是否有异常的成交量或价格行为

## 输出（仅返回 true 或 false）
true 表示需要深入分析，false 表示忽略""",
        },
        {
            "name": "Pinbar 预筛模板",
            "content": """你是一个 Pinbar 交易信号检测器。请快速判断当前 K 线是否包含有效的 Pinbar 信号。

## 策略规则
{strategy_rules}

## 当前窗口
{symbol} {timeframe}
K 线数据: {kline_data}

## 判断标准
1. 是否有明显的 Pinbar 形态（锤子线/射击之星）
2. 信号是否与策略入场条件一致
3. 是否在关键位附近

## 输出（仅返回 true 或 false）""",
        },
    ],
    "deep_analysis": [
        {
            "name": "默认深度分析模板",
            "content": """你是一个专业的 AI 交易分析师。基于完整的 K 线窗口和策略规则，进行深度分析。

## 策略规则
{strategy_rules}

## 市场数据
{symbol} {timeframe}
K 线窗口: {kline_data}

## 技术指标
{indicators}

## 账户状态
{account_status}

## 当前持仓
{position}

## 分析要求
1. 严格执行策略规则，不得超越策略允许的条件
2. 评估入场/出场时机
3. 设置合理的止损（基于策略指定方式）和止盈（1.5R~2R 盈亏比）
4. 明确仓位管理（基于策略仓位规则）

## 整体分析
{initial_analysis}

## 输出格式（JSON）
{{
    "market_analysis": {{
        "trend": "bullish | bearish | neutral",
        "strength": 1-5,
        "summary": "分析摘要"
    }},
    "trade_plan": {{
        "decision": "open_long | open_short | close_long | close_short | hold",
        "confidence": 1-100,
        "reason": "决策理由（必须引用策略规则）",
        "stop_loss": 止损价格,
        "take_profit": 止盈价格,
        "stop_loss_method": "策略规则止损 | Pinbar极值止损 | 固定百分比止损",
        "risk_reward_ratio": 1.5
    }},
    "key_levels": [
        {{"type": "support", "price": 数字}},
        {{"type": "resistance", "price": 数字}}
    ]
}}""",
        },
        {
            "name": "Pinbar 深度分析模板",
            "content": """你是一个基于裸 K 线 Pinbar 信号的交易分析师。请严格遵循策略规则进行深度分析。

## 策略规则（必须严格遵守）
{strategy_rules}

## 市场数据
{symbol} {timeframe}
K 线窗口: {kline_data}

## 技术指标
{indicators}

## 整体分析
{initial_analysis}

## 分析要求
1. 识别 Pinbar 形态（锤子线/上吊线/射击之星）
2. 判断 Pinbar 信号是否有效
3. 严格遵循策略入场条件
4. 止损设置在 Pinbar 极值 + 5% 缓冲
5. 止盈基于 1.5R~2R 盈亏比
6. 仓位管理遵循策略规则

## 输出格式（JSON）
{{
    "market_analysis": {{
        "trend": "bullish | bearish | neutral",
        "strength": 1-5,
        "summary": "分析摘要"
    }},
    "trade_plan": {{
        "decision": "open_long | open_short | hold",
        "confidence": 1-100,
        "reason": "决策理由",
        "stop_loss": 止损价格,
        "take_profit": 止盈价格,
        "stop_loss_method": "Pinbar极值止损",
        "risk_reward_ratio": 1.5
    }},
    "key_levels": []
}}""",
        },
    ],
}


class PromptTemplateService:
    """Prompt 模板 CRUD 业务。"""

    CATEGORIES = ("initial_analysis", "backtest_precheck", "deep_analysis")

    def __init__(self, db: AsyncSession):
        self.db = db

    async def seed_default_templates(self) -> int:
        """自动创建默认 Prompt 模板（仅在无模板时创建）。
        
        Returns: 创建的数量
        """
        result = await self.db.execute(select(PromptTemplate).limit(1))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return 0  # 已有模板，不覆盖

        count = 0
        for category, templates in DEFAULT_TEMPLATES.items():
            for tpl in templates:
                template = PromptTemplate(
                    category=category,
                    name=tpl["name"],
                    content=tpl["content"],
                    is_active=True,
                    version=1,
                )
                self.db.add(template)
                count += 1
        await self.db.flush()
        logger.info(f"Seeded {count} default prompt templates")
        return count

    async def list_templates(
        self, category: Optional[str] = None, active_only: bool = False
    ) -> Tuple[List[PromptTemplateResponse], int]:
        """获取模板列表（自动填充默认模板）。"""
        # 自动填充默认模板
        await self.seed_default_templates()
        
        query = select(PromptTemplate).order_by(PromptTemplate.created_at.desc())
        if category:
            query = query.where(PromptTemplate.category == category)
        if active_only:
            query = query.where(PromptTemplate.is_active == True)

        result = await self.db.execute(query)
        templates = result.scalars().all()
        return (
            [PromptTemplateResponse.model_validate(t) for t in templates],
            len(templates),
        )

    async def get_template(self, template_id: UUID) -> PromptTemplateResponse:
        """获取模板详情。"""
        template = await self.db.get(PromptTemplate, template_id)
        if not template:
            raise NotFoundException(message=f"Prompt 模板不存在: {template_id}")
        return PromptTemplateResponse.model_validate(template)

    async def create_template(self, data: PromptTemplateCreate) -> PromptTemplateResponse:
        """创建模板。"""
        template = PromptTemplate(
            category=data.category,
            name=data.name,
            content=data.content,
            is_active=data.is_active,
            version=1,
        )
        self.db.add(template)
        await self.db.flush()
        logger.info(f"Prompt template created: {template.id} ({data.category})")
        return PromptTemplateResponse.model_validate(template)

    async def update_template(
        self, template_id: UUID, data: PromptTemplateUpdate
    ) -> PromptTemplateResponse:
        """更新模板（版本号 +1）。"""
        template = await self.db.get(PromptTemplate, template_id)
        if not template:
            raise NotFoundException(message=f"Prompt 模板不存在: {template_id}")

        update_data = data.model_dump(exclude_unset=True)
        if update_data:
            update_data["version"] = template.version + 1
            stmt = (
                update(PromptTemplate)
                .where(PromptTemplate.id == template_id)
                .values(**update_data)
            )
            await self.db.execute(stmt)
            await self.db.flush()

        # 重新读取
        updated = await self.db.get(PromptTemplate, template_id)
        return PromptTemplateResponse.model_validate(updated)

    async def delete_template(self, template_id: UUID) -> None:
        """删除模板。"""
        template = await self.db.get(PromptTemplate, template_id)
        if not template:
            raise NotFoundException(message=f"Prompt 模板不存在: {template_id}")
        await self.db.delete(template)
        await self.db.flush()