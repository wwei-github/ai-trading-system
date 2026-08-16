"""AI Provider 工厂类。

管理多 Provider 的配置加载、实例创建、CRUD 操作。
配置持久化到 system_configs 表（category=ai, key=providers）。

支持 Provider 类型：
- openai_compatible：OpenAI 兼容接口
- ollama：Ollama 本地模型
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_api_key, encrypt_api_key
from app.models.audit import AuditLog
from app.services.llm_provider import (
    LLMProvider,
    NoopProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)


class ProviderFactory:
    """AI Provider 工厂类。

    从 system_configs 表加载 Provider 配置，
    创建对应的 LLMProvider 实例。
    """

    # ---------- 读取配置 ----------

    @staticmethod
    async def load_providers(db: AsyncSession) -> dict:
        """从 system_configs 加载所有 Provider 配置。"""
        from app.services.system_service import SystemService

        svc = SystemService(db)
        config = await svc.get_config_item("ai", "providers")
        if config is None:
            return {"active_provider_id": None, "providers": []}
        return config.value

    @staticmethod
    async def get_active_provider(db: AsyncSession) -> LLMProvider:
        """获取当前激活的 Provider 实例。"""
        data = await ProviderFactory.load_providers(db)
        active_id = data.get("active_provider_id")
        providers = data.get("providers", [])

        if not active_id or not providers:
            return NoopProvider("当前未配置 AI Provider")

        for p in providers:
            if p.get("id") == active_id:
                return ProviderFactory._create_provider(p)

        return NoopProvider("当前激活的 Provider 配置异常")

    @staticmethod
    async def get_provider_by_type(db: AsyncSession, provider_type: str) -> LLMProvider:
        """按类型获取第一个匹配的 Provider 实例。

        Args:
            db: 数据库会话
            provider_type: Provider 类型，如 "ollama"、"openai_compatible"

        Returns:
            LLMProvider 实例

        Raises:
            ValueError: 未找到匹配类型的 Provider
        """
        data = await ProviderFactory.load_providers(db)
        providers = data.get("providers", [])

        for p in providers:
            if p.get("type") == provider_type:
                return ProviderFactory._create_provider(p)

        raise ValueError(f"未找到类型为 '{provider_type}' 的 Provider")

    # ---------- 创建实例 ----------

    @staticmethod
    def _create_provider(provider_config: dict) -> LLMProvider:
        """根据配置创建 Provider 实例。"""
        ptype = provider_config.get("type", "")
        config = provider_config.get("config", {})

        if ptype == "openai_compatible":
            # 解密 API Key
            decrypted_config = dict(config)
            api_key_encrypted = config.get("api_key", "")
            if api_key_encrypted and api_key_encrypted != "****":
                try:
                    decrypted_config["api_key"] = decrypt_api_key(api_key_encrypted)
                except Exception:
                    logger.warning("API Key 解密失败，使用原始值")
            return OpenAICompatibleProvider(decrypted_config)
        elif ptype == "ollama":
            # 用运行时 OLLAMA_BASE_URL 覆盖 DB 中存储的 base_url
            # 这样用户切换本地/Docker 开发环境时无需修改 DB 配置
            ollama_config = dict(config)
            ollama_config["base_url"] = settings.OLLAMA_BASE_URL.rstrip("/")
            return OllamaProvider(ollama_config)
        return NoopProvider(f"未知的 Provider 类型: {ptype}")

    # ---------- 管理方法 ----------

    @staticmethod
    async def list_providers(db: AsyncSession) -> dict:
        """返回脱敏后的 Provider 列表。"""
        data = await ProviderFactory.load_providers(db)
        # 对所有 Provider 的 api_key 脱敏
        for p in data.get("providers", []):
            config = p.get("config", {})
            if "api_key" in config and config["api_key"]:
                config["api_key"] = "****"
        return data

    @staticmethod
    async def add_provider(
        db: AsyncSession,
        provider_data: dict,
        user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """添加 Provider（加密 API Key）。"""
        provider_id = f"provider-{uuid.uuid4().hex[:12]}"
        provider_data["id"] = provider_id
        provider_data["enabled"] = True
        provider_data["created_at"] = datetime.now(timezone.utc).isoformat()
        provider_data["updated_at"] = provider_data["created_at"]

        # 加密 API Key
        config = provider_data.get("config", {})
        if "api_key" in config and config["api_key"]:
            config["api_key"] = encrypt_api_key(config["api_key"])

        data = await ProviderFactory.load_providers(db)
        data["providers"].append(provider_data)
        if not data.get("active_provider_id"):
            data["active_provider_id"] = provider_id

        await ProviderFactory._save_providers(db, data)
        await db.commit()

        # 审计日志
        if user_id:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action="create",
                    resource_type="ai_provider",
                    resource_id=provider_id,
                    detail={
                        "provider_name": provider_data.get("name", ""),
                        "provider_type": provider_data.get("type", ""),
                    },
                )
            )
            await db.flush()

        return await ProviderFactory.list_providers(db)

    @staticmethod
    async def delete_provider(
        db: AsyncSession,
        provider_id: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """删除 Provider（禁止删除当前激活的）。"""
        data = await ProviderFactory.load_providers(db)
        if data.get("active_provider_id") == provider_id:
            from app.core.exceptions import BadRequestException

            raise BadRequestException(
                message="无法删除当前激活的 Provider，请先切换到其他 Provider"
            )

        provider = None
        for p in data["providers"]:
            if p.get("id") == provider_id:
                provider = p
                break

        data["providers"] = [p for p in data["providers"] if p.get("id") != provider_id]

        await ProviderFactory._save_providers(db, data)

        # 审计日志
        if user_id and provider:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action="delete",
                    resource_type="ai_provider",
                    resource_id=provider_id,
                    detail={
                        "provider_name": provider.get("name", ""),
                        "provider_type": provider.get("type", ""),
                    },
                )
            )
            await db.flush()

        return await ProviderFactory.list_providers(db)

    @staticmethod
    async def activate_provider(
        db: AsyncSession,
        provider_id: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """切换当前激活的 Provider。"""
        data = await ProviderFactory.load_providers(db)
        exists = any(p.get("id") == provider_id for p in data.get("providers", []))
        if not exists:
            from app.core.exceptions import NotFoundException

            raise NotFoundException(message=f"Provider 不存在: {provider_id}")

        data["active_provider_id"] = provider_id
        await ProviderFactory._save_providers(db, data)

        # 审计日志
        if user_id:
            db.add(
                AuditLog(
                    user_id=user_id,
                    action="update",
                    resource_type="ai_provider",
                    resource_id=provider_id,
                    detail={"action": "activate"},
                )
            )
            await db.flush()

        return await ProviderFactory.list_providers(db)

    # ---------- 持久化 ----------

    @staticmethod
    async def _save_providers(db: AsyncSession, data: dict) -> None:
        """保存 Provider 配置到 system_configs。"""
        from app.schemas.system import SystemConfigItemCreate
        from app.services.system_service import SystemService

        svc = SystemService(db)
        await svc.upsert_config_item(
            SystemConfigItemCreate(
                category="ai", key="providers", value=data
            )
        )

    # ---------- 迁移 ----------

    @staticmethod
    async def migrate_from_env(db: AsyncSession) -> None:
        """从环境变量迁移默认配置到 DB。

        首次启动时执行，将 .env 中的 LLM 配置迁移到 system_configs 表。
        后续启动时如果已有配置则跳过。
        """
        data = await ProviderFactory.load_providers(db)
        if data.get("providers"):
            logger.info("AI Provider 配置已存在，跳过迁移")
            return

        if settings.LLM_API_KEY:
            provider = {
                "id": f"provider-{uuid.uuid4().hex[:12]}",
                "type": "openai_compatible",
                "name": f"默认 ({settings.LLM_MODEL})",
                "enabled": True,
                "config": {
                    "api_key": encrypt_api_key(settings.LLM_API_KEY),
                    "base_url": settings.LLM_BASE_URL,
                    "model": settings.LLM_MODEL,
                    "temperature": settings.LLM_TEMPERATURE,
                    "max_tokens": settings.LLM_MAX_TOKENS,
                    "embedding_model": settings.EMBEDDING_MODEL,
                    "embedding_dimension": settings.EMBEDDING_DIMENSION,
                },
            }
            data = {"active_provider_id": provider["id"], "providers": [provider]}
            logger.info("从环境变量迁移 AI Provider 配置: {}", provider["name"])
        else:
            # 无 API Key 时，创建默认的 Ollama Provider（指向本地即可）
            provider = {
                "id": f"provider-{uuid.uuid4().hex[:12]}",
                "type": "ollama",
                "name": "Ollama 本地 (qwen3.5:9b)",
                "enabled": True,
                "config": {
                    "base_url": settings.OLLAMA_BASE_URL,
                    "model": "qwen3.5:9b",
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "embedding_model": "nomic-embed-text",
                },
            }
            data = {"active_provider_id": provider["id"], "providers": [provider]}
            logger.info("未配置 LLM_API_KEY，创建默认 Ollama Provider: {}", provider["name"])

        await ProviderFactory._save_providers(db, data)
        await db.commit()
        logger.info("AI Provider 配置已迁移到数据库")