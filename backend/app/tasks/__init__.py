"""Celery 异步任务应用配置。

使用 Redis 作为消息代理和结果后端。
"""

from celery import Celery

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
)

# 自动发现任务模块
celery_app.autodiscover_tasks(["app.tasks"])

__all__ = ["celery_app"]
