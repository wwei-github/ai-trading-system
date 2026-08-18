"""AI Provider 工厂。

云端 AI（OpenAI 兼容接口）完全由环境变量（LLM_*）配置，不在 UI 中管理。
本地模型（Ollama）配置持久化到 system_configs 表（category=ai, key=local_model），
用于 AI 回测的本地预筛。

API Key 完全通过环境变量 LLM_API_KEY 配置，不在 UI 中填写或展示。
"""

from typing import Dict, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.llm_provider import (
    LLMProvider,
    NoopProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)

# 本地模型默认配置
DEFAULT_LOCAL_MODEL_CONFIG: Dict = {
    "model": "qwen3.5:9b",
    "temperature": 0.7,
    "max_tokens": 4096,
    "embedding_model": "nomic-embed-text",
}


class ProviderFactory:
    """AI Provider 工厂。

    - 云端 AI：从环境变量创建 OpenAICompatibleProvider（LLM_* 配置）；
    - 本地模型：从 system_configs 表加载 Ollama 配置。
    """

    # ---------- 云端 AI（环境变量） ----------

    @staticmethod
    async def get_active_provider(db: AsyncSession) -> LLMProvider:
        """获取云端 AI Provider（完全由环境变量 LLM_* 配置）。

        Args:
            db: 数据库会话（保留参数以兼容调用方，云端 AI 不依赖 DB）。
        """
        if settings.LLM_API_KEY:
            return OpenAICompatibleProvider()
        return NoopProvider("未配置 LLM_API_KEY，请在环境变量中配置")

    # ---------- 本地模型（Ollama，持久化到 DB） ----------

    @staticmethod
    async def get_local_model_config(db: AsyncSession) -> dict:
        """获取本地模型配置（缺失时返回默认值）。"""
        from app.services.system_service import SystemService

        svc = SystemService(db)
        config = await svc.get_config_item("ai", "local_model")
        if config is None or not config.value:
            return dict(DEFAULT_LOCAL_MODEL_CONFIG)
        return dict(config.value)

    @staticmethod
    async def save_local_model_config(
        db: AsyncSession, config: Optional[dict]
    ) -> dict:
        """保存本地模型配置（只接受可配置字段，缺失项回退默认值）。"""
        from app.schemas.system import SystemConfigItemCreate
        from app.services.system_service import SystemService

        config = config or {}
        cleaned = {
            "model": (config.get("model") or "").strip()
            or DEFAULT_LOCAL_MODEL_CONFIG["model"],
            "temperature": (
                config.get("temperature")
                if config.get("temperature") is not None
                else DEFAULT_LOCAL_MODEL_CONFIG["temperature"]
            ),
            "max_tokens": config.get("max_tokens")
            or DEFAULT_LOCAL_MODEL_CONFIG["max_tokens"],
            "embedding_model": (config.get("embedding_model") or "").strip()
            or DEFAULT_LOCAL_MODEL_CONFIG["embedding_model"],
        }

        svc = SystemService(db)
        await svc.upsert_config_item(
            SystemConfigItemCreate(category="ai", key="local_model", value=cleaned)
        )
        await db.commit()
        return cleaned

    @staticmethod
    async def get_local_model_provider(db: AsyncSession) -> OllamaProvider:
        """获取本地 Ollama Provider（base_url 使用运行时 OLLAMA_BASE_URL）。"""
        config = await ProviderFactory.get_local_model_config(db)
        return OllamaProvider(
            {
                "base_url": settings.OLLAMA_BASE_URL.rstrip("/"),
                "model": config.get("model", "qwen3.5:9b"),
                "temperature": config.get("temperature", 0.7),
                "max_tokens": config.get("max_tokens", 8192),
                "embedding_model": config.get(
                    "embedding_model", "nomic-embed-text"
                ),
            }
        )

    @staticmethod
    async def ensure_local_model_config(db: AsyncSession) -> None:
        """启动时确保本地模型配置存在（首次创建默认值）。"""
        from app.services.system_service import SystemService

        svc = SystemService(db)
        config = await svc.get_config_item("ai", "local_model")
        if config is not None:
            logger.debug("本地模型配置已存在，跳过初始化")
            return

        await ProviderFactory.save_local_model_config(
            db, dict(DEFAULT_LOCAL_MODEL_CONFIG)
        )
        logger.info("已初始化本地模型配置: {}", DEFAULT_LOCAL_MODEL_CONFIG["model"])
