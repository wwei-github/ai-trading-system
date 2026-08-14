"""应用配置管理。

使用 pydantic-settings 从环境变量和 .env 文件加载配置。
"""

from functools import lru_cache
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置。"""

    # 应用基本信息
    APP_NAME: str = "AI Trading System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # 运行模式：
    #   - local    ：本地开发（SQLite + 内存缓存，不需要 Docker）
    #   - docker   ：Docker Compose 部署（PostgreSQL + Redis）
    #   - online   ：线上部署（PostgreSQL + Redis，由运维配置）
    RUN_MODE: str = "local"

    # 数据库（SQLite 或 PostgreSQL）
    # RUN_MODE=local 时，默认回退到 SQLite，可直接跑通后端；
    # RUN_MODE=docker/online 时，需要显式配置 PostgreSQL 地址。
    DATABASE_URL: str = (
        "postgresql+asyncpg://trading:trading@localhost:15432/trading"
    )

    # Redis（缓存 + Celery 消息代理 + 结果后端）
    # RUN_MODE=local 时，默认通过 fakeredis / 内存实现降级（在代码中自动判断），
    # 但如果设置了真实的 REDIS_URL，依然会使用真实 Redis。
    REDIS_URL: str = "redis://localhost:16379/0"

    # 安全配置
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # 加密密钥（用于派生 Fernet 密钥，生产环境必须更换）
    ENCRYPTION_KEY: str = "0123456789abcdef0123456789abcdef"

    # CORS 跨域配置
    CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:38000"]

    # ---------- Stage 1: JWT / 鉴权 ----------
    JWT_SECRET_KEY: str = ""  # 为空时回退到 SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REMEMBER_ME_DAYS: int = 30
    LOGIN_ATTEMPT_MAX: int = 5
    LOGIN_LOCK_MINUTES: int = 30

    # ---------- Stage 1: 邮件 SMTP ----------
    EMAIL_SMTP_HOST: str = ""
    EMAIL_SMTP_PORT: int = 465
    EMAIL_SMTP_USER: str = ""
    EMAIL_SMTP_PASSWORD: str = ""
    EMAIL_USE_TLS: bool = True
    EMAIL_FROM: str = "noreply@trading.local"
    EMAIL_TEST_MODE: bool = True  # True=控制台打印不实际发送
    APP_URL: str = "http://localhost:38000"  # 用于邮件链接

    # ---------- Stage 1: 限流 ----------
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_LOGIN_PER_MIN: int = 10
    RATE_LIMIT_TRADE_PER_MIN: int = 30
    RATE_LIMIT_AI_PER_MIN: int = 20
    RATE_LIMIT_UPLOAD_PER_MIN: int = 3

    # 数据库连接池
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    # 默认用户 ID（无认证场景下，所有数据归属于此用户）
    # 启动时若不存在会自动创建
    DEFAULT_USER_ID: str = "00000000-0000-0000-0000-000000000001"
    DEFAULT_USER_EMAIL: str = "admin@trading-system.dev"
    DEFAULT_USER_NICKNAME: str = "Trader"

    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB

    # LLM 配置（OpenAI 兼容接口）
    LLM_PROVIDER: str = "openai"  # openai / anthropic / custom
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000

    # Embedding 配置（用于书籍 RAG）
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # ---------- Stage 9: 交易所代理 ----------
    # 交易所 API 请求代理地址（大陆需配置才能访问 Binance 等境外交易所）
    # 格式: http://127.0.0.1:7890 或 https://user:pass@proxy:port
    EXCHANGE_PROXY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---------- 运行模式派生规则 ----------

    def effective_database_url(self) -> str:
        """根据 RUN_MODE 派生实际数据库 URL。

        RUN_MODE=local 且未配置 PostgreSQL 时，回退到 SQLite（aiosqlite），
        从而不需要 Docker 也能直接启动后端。
        """
        # 如果用户显式设置了非默认的 PostgreSQL URL，优先使用用户配置
        default_pg = "postgresql+asyncpg://trading:trading@localhost:15432/trading"
        if self.RUN_MODE == "local" and self.DATABASE_URL == default_pg:
            import os

            db_file = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "trading.db")
            )
            # 异步 SQLite 使用 aiosqlite 驱动（注意 +aiosqlite 后缀）
            return f"sqlite+aiosqlite:///{db_file}"
        return self.DATABASE_URL

    def uses_sqlite(self) -> bool:
        """判断是否正在使用 SQLite（影响某些特性，如 pgvector）。"""
        return self.effective_database_url().startswith("sqlite")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """解析 CORS_ORIGINS，支持 JSON 数组字符串或逗号分隔字符串。"""
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # 按逗号分隔
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()


settings = get_settings()
