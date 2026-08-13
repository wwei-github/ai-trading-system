"""FastAPI 应用入口。

创建 FastAPI 应用，配置中间件、异常处理和路由注册。
"""

import time
import uuid as uuid_lib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import select

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging


async def _initialize_storage() -> None:
    """启动时数据库初始化：
    - SQLite：自动 CREATE ALL 建表（local 模式零依赖）
    - PostgreSQL：假设已由 alembic upgrade head 建表，只做默认用户补齐
    - 任何数据库：若默认用户不存在，自动创建
    """
    from app.core.database import async_session_maker, engine
    from app.models import Base, User

    # SQLite：自动建表
    if settings.uses_sqlite():
        logger.info("RUN_MODE=local，使用 SQLite 自动建表")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # 自动补齐默认用户
    async with async_session_maker() as session:
        try:
            default_uid = uuid_lib.UUID(settings.DEFAULT_USER_ID)
        except Exception:
            logger.warning("DEFAULT_USER_ID 不是合法 UUID，跳过默认用户创建")
            return
        result = await session.execute(
            select(User).where(User.id == default_uid)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                id=default_uid,
                email=settings.DEFAULT_USER_EMAIL,
                nickname=settings.DEFAULT_USER_NICKNAME,
                is_active=True,
                role="admin",
            )
            session.add(user)
            await session.commit()
            logger.info(
                "默认用户已创建 | id={} email={}",
                settings.DEFAULT_USER_ID,
                settings.DEFAULT_USER_EMAIL,
            )
        else:
            logger.debug("默认用户已存在 | id={}", settings.DEFAULT_USER_ID)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    启动时初始化日志 + 数据库建表/默认用户，关闭时清理资源。
    """
    # 初始化日志
    setup_logging()
    logger.info(
        "应用启动: {} | 环境: {} | RUN_MODE: {}",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.RUN_MODE,
    )

    # 存储初始化（建表 + 默认用户）
    try:
        await _initialize_storage()
    except Exception as exc:
        logger.exception("存储初始化失败：{}", exc)

    yield

    # 关闭时清理
    logger.info("应用关闭")
    from app.core.database import engine

    await engine.dispose()


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    app = FastAPI(
        title=settings.APP_NAME,
        description="AI 智能交易管理系统后端 API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS 配置
    cors_origins = settings.CORS_ORIGINS
    if isinstance(cors_origins, str):
        cors_origins = [cors_origins]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """记录请求日志和响应时间。"""
        start_time = time.time()

        # 请求信息
        logger.info(
            "请求 | {} {} | 客户端: {}",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
        )

        response = await call_next(request)

        # 响应时间
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "响应 | {} {} | 状态: {} | 耗时: {:.2f}ms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response

    # 注册异常处理器
    register_exception_handlers(app)

    # 注册路由
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # 根路由
    @app.get("/", summary="根路由")
    async def root():
        """返回应用基本信息。"""
        return {
            "app_name": settings.APP_NAME,
            "version": "1.0.0",
            "environment": settings.APP_ENV,
            "docs_url": "/docs",
            "api_prefix": settings.API_PREFIX,
        }

    # 应用级健康检查
    @app.get("/health", summary="应用健康检查")
    async def health():
        """应用整体健康检查。"""
        return JSONResponse(
            content={
                "code": 0,
                "message": "ok",
                "data": {
                    "status": "healthy",
                    "app_name": settings.APP_NAME,
                    "environment": settings.APP_ENV,
                },
            }
        )

    return app


# 创建应用实例
app = create_app()
