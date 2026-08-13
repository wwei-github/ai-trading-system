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

    # 数据库
    DATABASE_URL: str = (
        "postgresql+asyncpg://trading:trading@localhost:5432/trading"
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # 安全配置
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # 加密密钥（AES-256，32 字节十六进制字符串）
    ENCRYPTION_KEY: str = "0123456789abcdef0123456789abcdef"

    # CORS 跨域配置
    CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:5173"]

    # 数据库连接池
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

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
