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

    # 数据库（PostgreSQL 异步驱动 asyncpg）
    DATABASE_URL: str = (
        "postgresql+asyncpg://trading:trading@localhost:15432/trading"
    )

    # Redis（缓存 + Celery 消息代理 + 结果后端）
    REDIS_URL: str = "redis://localhost:16379/0"

    # 安全配置
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # 加密密钥（用于派生 Fernet 密钥，生产环境必须更换）
    ENCRYPTION_KEY: str = "0123456789abcdef0123456789abcdef"

    # CORS 跨域配置
    CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:38000"]

    # 数据库连接池
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    # 默认用户 ID（无认证场景下，所有数据归属于此用户）
    # 启动时若不存在会自动创建
    DEFAULT_USER_ID: str = "00000000-0000-0000-0000-000000000001"
    DEFAULT_USER_EMAIL: str = "admin@trading.local"
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

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
