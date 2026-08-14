"""数据库连接管理。

使用 SQLAlchemy 2.0 异步引擎，采用延迟连接策略，
即使数据库未启动也不会影响应用启动。
"""

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _build_engine_kwargs() -> dict:
    """根据 RUN_MODE 动态构造 create_async_engine 参数。

    - SQLite：不支持连接池，使用 StaticPool，数据库文件不存在自动创建。
    - PostgreSQL：使用 QueuePool + 连接池参数。
    """
    database_url = settings.effective_database_url()
    common = {
        "url": database_url,
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
    }
    if settings.uses_sqlite():
        from sqlalchemy.pool import StaticPool

        return {
            **common,
            "connect_args": {
                "check_same_thread": False,
                # SQLite 默认不支持外键级联，手动开启
            },
            "poolclass": StaticPool,
        }
    return {
        **common,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    }


# 创建异步引擎（延迟连接，pool_pre_ping 在实际使用时才检测连接）
engine = create_async_engine(**_build_engine_kwargs())

# 异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖。

    作为 FastAPI 依赖注入使用，自动管理会话生命周期。
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """检查数据库连接是否正常。

    用于健康检查，连接失败时返回 False 而不抛出异常。
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ---------- Redis 客户端（带降级；连不上时返回 None，业务可优雅跳过缓存） ----------

redis_client = None

try:
    if not settings.uses_sqlite():
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
except Exception:
    # Redis 未启动或未安装 redis 包时，保持 None；业务层需做 None 检查
    redis_client = None


async def check_redis_connection() -> bool:
    """检查 Redis 连接是否正常。"""
    if redis_client is None:
        return False
    try:
        await redis_client.ping()
        return True
    except Exception:
        return False
