"""Celery 异步任务应用配置。

使用 Redis 作为消息代理和结果后端。
配置 Celery Beat 定时调度周期任务。
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# 创建 Celery 应用
celery_app = Celery(
    "ai_trading",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Celery 配置
celery_app.conf.update(
    # 时区
    timezone="UTC",
    enable_utc=True,
    # 序列化
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # 结果过期时间（1 小时）
    result_expires=3600,
    # 任务超时
    task_time_limit=3600,
    task_soft_time_limit=3000,
    # 重试配置
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # 队列配置：长任务（回测、报告）使用独立队列避免阻塞数据同步
    task_routes={
        "run_backtest": {"queue": "backtest"},
        "generate_report": {"queue": "report"},
        "parse_book": {"queue": "celery"},
        "sync_trades": {"queue": "celery"},
        "sync_asset_snapshot": {"queue": "celery"},
        "sync_all_accounts": {"queue": "celery"},
        "paper_trading_tick": {"queue": "celery"},
        "live_signal_tick": {"queue": "celery"},
        "monitor_live_risk": {"queue": "celery"},
    },
    # Celery Beat 定时调度
    beat_schedule={
        # 每 15 分钟同步所有活跃账号数据
        "sync-all-accounts-every-15-min": {
            "task": "sync_all_accounts",
            "schedule": crontab(minute="*/15"),
        },
        # 每小时记录所有活跃账号资产快照（通过 sync_all_accounts 间接调用，
        # 此处单独定义以便精细化控制，需要时启用）
        "sync-asset-snapshot-hourly": {
            "task": "sync_all_accounts",
            "schedule": crontab(minute=0),
        },
        # 每 2 分钟处理模拟交易信号（Stage 6.6）
        "paper-trading-tick-every-2-min": {
            "task": "paper_trading_tick",
            "schedule": crontab(minute="*/2"),
        },
        # 每 2 分钟处理实盘信号生成（Stage 6.7）
        "live-signal-tick-every-2-min": {
            "task": "live_signal_tick",
            "schedule": crontab(minute="*/2"),
        },
        # 每分钟风控监控（Stage 9.2）：日亏/回撤达标自动止停 + 告警
        "monitor-live-risk-every-minute": {
            "task": "monitor_live_risk",
            "schedule": crontab(minute="*"),
        },
    },
)

# 自动发现任务模块
celery_app.autodiscover_tasks(["app.tasks"])

# 显式导入所有任务模块，确保 Celery worker 正确注册
from app.tasks import (
    book_tasks,
    sync_tasks,
    backtest_tasks,
    paper_trading_tasks,
    report_tasks,
    risk_monitor_tasks,
)

__all__ = ["celery_app"]
