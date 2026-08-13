"""分析报告生成任务。

由用户请求派发，负责：
1. 根据报告类型从数据库汇总数据（交易 / 策略 / 投资组合）
2. 调用 LLM 生成 Markdown 格式报告
3. 返回报告内容（结果存于 Celery 结果后端）
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from loguru import logger

from app.tasks import celery_app


async def _gather_trade_data(
    user_id: uuid.UUID,
    start_date: Optional[str],
    end_date: Optional[str],
) -> Dict[str, Any]:
    """汇总交易数据。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.trade import Trade

    async with async_session_maker() as session:
        stmt = select(Trade).where(Trade.user_id == user_id)
        if start_date:
            stmt = stmt.where(Trade.executed_at >= start_date)
        if end_date:
            stmt = stmt.where(Trade.executed_at <= end_date)
        result = await session.execute(stmt.order_by(Trade.executed_at.desc()))
        trades = list(result.scalars().all())

    if not trades:
        return {"total_trades": 0, "message": "指定时间范围内无交易记录"}

    total_volume = sum(float(t.price) * float(t.quantity) for t in trades)
    total_fee = sum(float(t.fee or 0) for t in trades)
    buy_count = sum(1 for t in trades if t.side == "buy")
    sell_count = sum(1 for t in trades if t.side == "sell")
    symbols = list({t.symbol for t in trades})
    exchanges = list({t.exchange for t in trades})

    return {
        "total_trades": len(trades),
        "total_volume": round(total_volume, 2),
        "total_fee": round(total_fee, 2),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "symbols": symbols[:20],  # 限制长度避免 token 超限
        "exchanges": exchanges,
        "first_trade_at": trades[-1].executed_at.isoformat() if trades else None,
        "last_trade_at": trades[0].executed_at.isoformat() if trades else None,
    }


async def _gather_strategy_data(user_id: uuid.UUID) -> Dict[str, Any]:
    """汇总策略数据。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.backtest import Backtest
    from app.models.strategy import Strategy

    async with async_session_maker() as session:
        result = await session.execute(
            select(Strategy).where(Strategy.user_id == user_id)
        )
        strategies = list(result.scalars().all())

        if not strategies:
            return {"total_strategies": 0, "message": "无策略记录"}

        # 获取回测结果
        strategy_ids = [s.id for s in strategies]
        bt_result = await session.execute(
            select(Backtest)
            .where(Backtest.strategy_id.in_(strategy_ids))
            .order_by(Backtest.created_at.desc())
        )
        backtests = list(bt_result.scalars().all())

    return {
        "total_strategies": len(strategies),
        "active_strategies": sum(1 for s in strategies if s.status == "active"),
        "categories": list({s.category for s in strategies}),
        "total_backtests": len(backtests),
        "completed_backtests": sum(
            1 for b in backtests if b.status == "completed"
        ),
        "strategies": [
            {
                "name": s.name,
                "category": s.category,
                "status": s.status,
            }
            for s in strategies[:20]
        ],
    }


async def _gather_portfolio_data(user_id: uuid.UUID) -> Dict[str, Any]:
    """汇总投资组合数据。"""
    from sqlalchemy import select

    from app.core.database import async_session_maker
    from app.models.asset import AssetSnapshot
    from app.models.account import ExchangeAccount

    async with async_session_maker() as session:
        # 账号
        acc_result = await session.execute(
            select(ExchangeAccount).where(
                ExchangeAccount.user_id == user_id,
                ExchangeAccount.status == "active",
            )
        )
        accounts = list(acc_result.scalars().all())

        # 最近资产快照
        snap_result = await session.execute(
            select(AssetSnapshot)
            .where(AssetSnapshot.user_id == user_id)
            .order_by(AssetSnapshot.snapshot_at.desc())
            .limit(30)
        )
        snapshots = list(snap_result.scalars().all())

    latest = float(snapshots[0].total_usd) if snapshots else 0.0
    first = float(snapshots[-1].total_usd) if snapshots else 0.0
    growth = ((latest - first) / first) if first > 0 else 0.0

    return {
        "total_accounts": len(accounts),
        "exchanges": list({a.exchange for a in accounts}),
        "latest_total_usd": round(latest, 2),
        "first_total_usd": round(first, 2),
        "growth": round(growth, 4),
        "snapshot_count": len(snapshots),
    }


async def _generate_report_async(
    user_id: str,
    report_type: str,
    start_date: Optional[str],
    end_date: Optional[str],
    context: Optional[Dict[str, Any]],
) -> dict:
    """异步生成报告。"""
    from app.services.llm_provider import get_llm_provider

    user_uuid = uuid.UUID(user_id)

    # 1. 汇总数据
    if report_type == "strategy":
        data = await _gather_strategy_data(user_uuid)
        data_title = "策略评估报告"
    elif report_type == "portfolio":
        data = await _gather_portfolio_data(user_uuid)
        data_title = "投资组合报告"
    else:
        data = await _gather_trade_data(user_uuid, start_date, end_date)
        data_title = "交易表现分析报告"

    # 2. 调用 LLM
    llm = get_llm_provider()
    messages = [
        {
            "role": "system",
            "content": (
                "你是一位专业的交易分析报告撰写专家。"
                "请根据提供的数据生成一份结构化的分析报告，"
                "包含：1. 概述 2. 关键指标分析 3. 趋势分析 4. 风险评估 5. 改进建议。"
                "使用 Markdown 格式输出。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"报告类型：{data_title}\n"
                f"时间范围：{start_date or '全部'} 至 {end_date or '至今'}\n"
                f"附加上下文：{json.dumps(context, ensure_ascii=False) if context else '无'}\n\n"
                f"数据：\n{json.dumps(data, ensure_ascii=False, indent=2, default=str)}\n\n"
                "请生成详细的分析报告。"
            ),
        },
    ]
    content = await llm.chat(messages)

    return {
        "report_type": report_type,
        "title": data_title,
        "content": content,
        "data_summary": data,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="generate_report", bind=True)
def generate_report(
    self,
    user_id: str,
    report_type: str = "trade",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> dict:
    """生成分析报告。

    Args:
        user_id: 用户 ID（字符串形式 UUID）
        report_type: 报告类型：trade / strategy / portfolio
        start_date: 起始日期（ISO 字符串）
        end_date: 结束日期（ISO 字符串）
        context: 附加上下文

    Returns:
        报告内容字典
    """
    logger.info(
        "开始生成报告 | user_id={} type={} task_id={}",
        user_id,
        report_type,
        self.request.id,
    )
    return asyncio.run(
        _generate_report_async(
            user_id, report_type, start_date, end_date, context
        )
    )
