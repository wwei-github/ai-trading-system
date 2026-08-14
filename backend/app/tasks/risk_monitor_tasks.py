"""实盘风控监控任务（Stage 9.2，对齐 PRD §5.6.5 R3）。

定时扫描所有 running 状态的实盘策略实例：
- 当日亏损达标 → 自动停止策略 + 告警邮件
- 策略累计回撤达标 → 自动停止策略 + 告警邮件
- 账号连接异常 → 重试 3 次 → 停止并告警

由 Celery Beat 每分钟触发。
"""

import asyncio

from loguru import logger

from app.tasks import celery_app


async def _monitor_live_risk_async() -> dict:
    """异步执行风控监控。"""
    from app.core.database import async_session_maker
    from app.services.risk_service import RiskMonitor

    stopped_count = 0
    checked_count = 0

    async with async_session_maker() as session:
        monitor = RiskMonitor(session)
        actions = await monitor.monitor_all_instances()
        checked_count = len(actions)  # actions 是触发的，不是检查的总数

        if actions:
            for action in actions:
                logger.warning(
                    "风控止停 | instance={} reason={} action={}",
                    action["instance_id"],
                    action["reason"],
                    action["action"],
                )
                stopped_count += 1

            # 提交事务（止停状态变更 + 审计日志）
            await session.commit()

    logger.info(
        "风控监控完成 | 触发止停={} 检查动作={}",
        stopped_count,
        checked_count,
    )
    return {
        "stopped": stopped_count,
        "actions": checked_count,
    }


@celery_app.task(name="monitor_live_risk", bind=True)
def monitor_live_risk(self) -> dict:
    """定时风控监控（由 Celery Beat 每分钟触发）。

    扫描所有 running 状态的实盘策略实例，
    对触发风控阈值的实例自动止停并发送告警邮件。
    """
    logger.info("开始风控监控 | task={}", self.request.id)
    try:
        return asyncio.run(_monitor_live_risk_async())
    except Exception as e:
        logger.exception("风控监控任务异常 | task={} err={}", self.request.id, e)
        raise
