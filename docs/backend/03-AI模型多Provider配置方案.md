# 03 AI 模型多 Provider 配置方案

| 项目     | 内容                                              |
| -------- | ------------------------------------------------- |
| 文档版本 | v2.0                                              |
| 编写日期 | 2026-08-14                                        |
| 状态     | 设计稿                                            |
| 涉及模块 | 后端 AI 服务、系统配置、前端系统设置、Docker 编排 |

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [整体架构](#2-整体架构)
3. [Provider 类型设计](#3-provider-类型设计)
4. [系统配置持久化方案](#4-系统配置持久化方案)
5. [后端实现细节](#5-后端实现细节)
6. [前端交互设计](#6-前端交互设计)
7. [Docker 编排（Ollama 部署）](#7-docker-编排ollama-部署)
8. [API 接口变更清单](#8-api-接口变更清单)
9. [迁移与兼容性](#9-迁移与兼容性)
10. [风险与应对](#10-风险与应对)
11. [实现优先级](#11-实现优先级)

---

## 1. 背景与目标

### 1.1 现状

当前系统仅支持 **OpenAI 兼容接口** 一种 Provider，配置通过 `backend/.env` 环境变量注入，启动后不可变：

```ini
LLM_PROVIDER=openai
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

`llm_provider.py` 使用单例模式，启动时一次性加载环境变量，无法在运行时切换。

### 1.2 需求

1. **API Key 模式**（OpenAI 兼容接口）：用户可在管理系统页面**添加/删除/编辑**多个 API Key 配置（如 OpenAI、Azure、本地 vLLM 等），支持运行时切换，无需重启后端
2. **Ollama 本地模型**：部署在 Docker 中，通过 Ollama HTTP API 调用，可在前端切换使用
3. **前端切换**：在系统设置页提供 AI Provider 管理 UI，用户可：
   - 查看所有已配置的 Provider 列表
   - 添加/删除/编辑 API Key 类型的 Provider 配置
   - 一键切换当前激活的 Provider
   - 选择 Ollama 的模型名称（如 `qwen2.5`, `llama3.2` 等）

### 1.3 设计目标

| 目标       | 说明                                                                      |
| ---------- | ------------------------------------------------------------------------- |
| 运行时切换 | 切换 Provider 无需重启后端，当前活跃会话不受影响（新消息使用新 Provider） |
| 配置持久化 | Provider 配置写入 `system_configs` 表，启动时自动从环境变量迁移           |
| 前端可管理 | 全部 Provider 管理操作在系统设置 UI 完成                                  |
| 安全存储   | API Key 加密存储到 DB（复用 `app/core/security.py` 中的脱敏函数）         |
| 降级兜底   | 无可用 Provider 时返回明确错误提示，不崩溃                                |

---

## 2. 整体架构

### 2.1 架构图

```
┌───────────────┐     ┌──────────────────────────────────────────┐
│  前端系统设置  │     │              后端 API                    │
│  (AI Provider  │     │                                          │
│   管理页面)    │     │  ┌────────────────────────────────────┐  │
│               │────▶│  │ POST /api/v1/ai/providers          │  │
│               │     │  │ DELETE /api/v1/ai/providers/{id}   │  │
│               │     │  │ POST /api/v1/ai/providers/{id}/    │  │
│               │     │  │   activate                         │  │
│               │     │  └────────────────────────────────────┘  │
│               │     │  ┌────────────────────────────────────┐  │
│  AI 对话页    │     │  │ ProviderFactory                   │  │
│  (Provider     │     │  │  ├─ load_providers(db) → 从 DB 读取│  │
│   选择器)     │────▶│  │  ├─ get_active_provider(db)        │  │
│               │     │  │  └─ create_provider(config)        │  │
│               │     │  └────────────────────────────────────┘  │
│               │     │  ┌────────────────────────────────────┐  │
│               │     │  │ AIService                         │  │
│               │     │  │  ├─ send_message()                │  │
│               │     │  │  ├─ stream_message()              │  │
│               │     │  │  ├─ generate_signal()             │  │
│               │     │  │  └─ generate_report()             │  │
│               │     │  └────────────────────────────────────┘  │
└───────────────┘     └──────────┬───────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
            ┌──────────┐  ┌──────────┐  ┌──────────┐
            │ OpenAI   │  │ 自定义   │  │ Ollama   │
            │ 兼容API  │  │ API Key  │  │ 本地模型  │
            │ (远程)   │  │ (远程)   │  │ (Docker) │
            └──────────┘  └──────────┘  └──────────┘
```

### 2.2 核心变化对照

| 维度            | 当前实现                                | 改造后                                                     |
| --------------- | --------------------------------------- | ---------------------------------------------------------- |
| Provider 来源   | `.env` 环境变量                         | `system_configs` 表（`category=ai`）                       |
| Provider 实例化 | `get_llm_provider()` 单例（启动时创建） | `ProviderFactory.get_active_provider(db)` 每次请求动态创建 |
| 切换方式        | 修改 `.env` + 重启                      | API 调用，即时生效                                         |
| 支持类型        | 仅 OpenAI 兼容                          | OpenAI 兼容 + Ollama                                       |
| 前端配置        | 无                                      | 专用管理页面，CRUD + 切换                                  |

---

## 3. Provider 类型设计

### 3.1 Provider 类型枚举

| 类型标识            | 名称            | 说明                                        | 必填配置项                     |
| ------------------- | --------------- | ------------------------------------------- | ------------------------------ |
| `openai_compatible` | OpenAI 兼容接口 | 任何兼容 OpenAI Chat Completions API 的服务 | `api_key`, `base_url`, `model` |
| `ollama`            | Ollama 本地模型 | 部署在 Docker 中的 Ollama 服务              | `base_url`, `model`            |

### 3.2 Provider 配置结构（JSONB）

每条 Provider 记录在 `system_configs` 表的 `value` 字段中：

```jsonc
// OpenAI 兼容接口类型
{
  "id": "provider-uuid-1",
  "type": "openai_compatible",
  "name": "OpenAI GPT-4o",
  "enabled": true,
  "config": {
    "api_key": "sk-encrypted-base64...",  // 加密存储
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 2000,
    "embedding_model": "text-embedding-3-small",
    "embedding_dimension": 1536
  },
  "created_at": "2026-08-14T10:00:00Z",
  "updated_at": "2026-08-14T10:00:00Z"
}

// Ollama 本地模型类型
{
  "id": "provider-uuid-2",
  "type": "ollama",
  "name": "Ollama 本地",
  "enabled": true,
  "config": {
    "base_url": "http://ollama:11434",
    "model": "qwen3.5:7b",
    "temperature": 0.7,
    "max_tokens": 4096,
    "embedding_model": "nomic-embed-text",   // Ollama 的 embedding 模型
    "embedding_dimension": 768
  },
  "created_at": "2026-08-14T10:00:00Z",
  "updated_at": "2026-08-14T10:00:00Z"
}
```

### 3.3 系统配置表存储设计

`system_configs` 表使用 `category="ai"` + `key="providers"` 一条记录存储所有 Provider 配置：

```jsonc
// category="ai", key="providers"
{
  "active_provider_id": "provider-uuid-1", // 当前激活的 Provider ID
  "providers": [
    {
      /* Provider 1 */
    },
    {
      /* Provider 2 */
    },
  ],
}
```

**为什么用一条记录存所有 Provider？**

| 考量         | 说明                                               |
| ------------ | -------------------------------------------------- |
| 原子性更新   | 增删改 Provider 时一次写入，避免多记录事务         |
| 前端展示简单 | 一次 GET 拿到全部 Provider 列表 + 当前激活状态     |
| 切换操作简单 | 只改 `active_provider_id` 字段                     |
| 删除安全     | 操作时可以直接检查 `active_provider_id` 并拒绝删除 |

---

## 4. 系统配置持久化方案

### 4.1 API 端点

| 方法     | 路径                                          | 说明                                            | 鉴权       |
| -------- | --------------------------------------------- | ----------------------------------------------- | ---------- |
| `GET`    | `/api/v1/ai/providers`                        | 获取所有 Provider 配置 + 当前激活的 provider_id | ✅ Trader+ |
| `POST`   | `/api/v1/ai/providers`                        | 添加新的 Provider（API Key 加密存储）           | ✅ Admin   |
| `PATCH`  | `/api/v1/ai/providers/{provider_id}`          | 编辑 Provider 配置                              | ✅ Admin   |
| `DELETE` | `/api/v1/ai/providers/{provider_id}`          | 删除 Provider（不可删除当前激活的）             | ✅ Admin   |
| `POST`   | `/api/v1/ai/providers/{provider_id}/activate` | 切换当前激活的 Provider                         | ✅ Trader+ |
| `POST`   | `/api/v1/ai/providers/ollama/models`          | 测试连接 Ollama 并获取可用模型列表              | ✅ Trader+ |

### 4.2 数据流

```
添加 Provider:
  前端 POST /ai/providers { type, name, config }
  → 后端校验配置合法性
  → 若 type=openai_compatible，加密 api_key
  → 写入 system_configs (category=ai, key=providers) 的 providers 数组
  → 返回完整 Provider 列表（api_key 脱敏为 "****"）

切换 Provider:
  前端 POST /ai/providers/{id}/activate
  → 后端校验 Provider 存在且 enabled
  → 更新 active_provider_id
  → 下次 AIService._get_llm() 调用时从 DB 重新加载
  → 即时生效（无需重启）

删除 Provider:
  前端 DELETE /ai/providers/{id}
  → 检查是否为 active_provider → 是则返回 400 "请先切换到其他 Provider"
  → 从 providers 数组中移除
  → 返回更新后的列表

获取 Ollama 模型列表:
  前端 POST /ai/providers/ollama/models { base_url }
  → 后端请求 Ollama API: GET {base_url}/api/tags
  → 返回可用模型列表 [{ name, size, modified_at }]
```

### 4.3 安全要求

| 要求             | 实现                                                                           |
| ---------------- | ------------------------------------------------------------------------------ |
| API Key 加密存储 | 存储前使用 `AESGCM` 加密（复用 `app/core/security.py` 的 `encrypt`/`decrypt`） |
| 响应脱敏         | 响应中 `api_key` 始终返回 `"****"`，编辑时前端提示"留空不修改"                 |
| 审计日志         | 记录所有 Provider 添加/删除/切换操作到 `audit_logs` 表                         |
| 权限控制         | 仅 Admin 角色可增删改；Trader+ 可查看和切换                                    |

---

## 5. 后端实现细节

### 5.1 新增文件：`app/services/provider_factory.py`

```python
"""AI Provider 工厂，动态从 DB 配置创建 Provider 实例。

替代原有的 get_llm_provider() 单例。
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.system_service import SystemService
from app.services.llm_provider import (
    LLMProvider,
    OpenAICompatibleProvider,
    OllamaProvider,
    NoopProvider,
)


class ProviderFactory:
    """AI Provider 工厂类。"""

    PROVIDERS_CONFIG_KEY = "ai"      # system_configs.category
    PROVIDERS_CONFIG_VALUE_KEY = "providers"  # system_configs.key

    # ── 读取 ──

    @staticmethod
    async def load_providers(db: AsyncSession) -> dict:
        """从 system_configs 加载所有 AI Provider 配置。

        Returns:
            {
                "active_provider_id": "uuid" | None,
                "providers": [ ... ]
            }
        """
        svc = SystemService(db)
        config = await svc.get_config_item(
            ProviderFactory.PROVIDERS_CONFIG_KEY,
            ProviderFactory.PROVIDERS_CONFIG_VALUE_KEY,
        )
        if config is None:
            return {"active_provider_id": None, "providers": []}
        return config.value

    @staticmethod
    async def get_active_provider(db: AsyncSession) -> LLMProvider:
        """获取当前激活的 Provider 实例。"""
        data = await ProviderFactory.load_providers(db)
        active_id = data.get("active_provider_id")
        if not active_id:
            return NoopProvider("未配置任何 AI Provider，请前往系统设置添加")

        providers = data.get("providers", [])
        for p in providers:
            if p.get("id") == active_id:
                return ProviderFactory._create_provider(p)

        return NoopProvider(f"当前激活的 Provider ({active_id}) 不存在或已被删除")

    @staticmethod
    def _create_provider(provider_config: dict) -> LLMProvider:
        """根据配置创建 Provider 实例。"""
        ptype = provider_config.get("type", "")
        config = provider_config.get("config", {})
        if ptype == "openai_compatible":
            return OpenAICompatibleProvider(config)
        elif ptype == "ollama":
            return OllamaProvider(config)
        return NoopProvider(f"未知的 Provider 类型: {ptype}")

    # ── 管理 ──

    @staticmethod
    async def list_providers(db: AsyncSession) -> dict:
        """返回所有 Provider 摘要（api_key 已脱敏）。"""
        data = await ProviderFactory.load_providers(db)
        # 脱敏处理
        for p in data.get("providers", []):
            cfg = p.get("config", {})
            if "api_key" in cfg and cfg["api_key"]:
                cfg["api_key"] = "****"
        return data

    @staticmethod
    async def add_provider(
        db: AsyncSession, provider_data: dict
    ) -> dict:
        """添加一个新的 Provider。"""
        # 生成 ID
        provider_data["id"] = f"provider-{uuid.uuid4().hex[:12]}"
        provider_data["enabled"] = True
        provider_data["created_at"] = datetime.now(timezone.utc).isoformat()
        provider_data["updated_at"] = provider_data["created_at"]

        # 加密 api_key
        config = provider_data.get("config", {})
        if "api_key" in config and config["api_key"]:
            config["api_key"] = ProviderFactory._encrypt(config["api_key"])

        # 写入 DB
        svc = SystemService(db)
        data = await ProviderFactory.load_providers(db)
        data["providers"].append(provider_data)
        if not data.get("active_provider_id"):
            data["active_provider_id"] = provider_data["id"]

        await svc.upsert_config_item(
            category=ProviderFactory.PROVIDERS_CONFIG_KEY,
            key=ProviderFactory.PROVIDERS_CONFIG_VALUE_KEY,
            value=data,
        )
        return ProviderFactory.list_providers(db)

    @staticmethod
    async def delete_provider(db: AsyncSession, provider_id: str) -> dict:
        """删除 Provider。"""
        data = await ProviderFactory.load_providers(db)
        if data.get("active_provider_id") == provider_id:
            raise ValueError("无法删除当前激活的 Provider，请先切换到其他 Provider")

        data["providers"] = [p for p in data["providers"] if p.get("id") != provider_id]

        svc = SystemService(db)
        await svc.upsert_config_item(
            category=ProviderFactory.PROVIDERS_CONFIG_KEY,
            key=ProviderFactory.PROVIDERS_CONFIG_VALUE_KEY,
            value=data,
        )
        return ProviderFactory.list_providers(db)

    @staticmethod
    async def activate_provider(db: AsyncSession, provider_id: str) -> dict:
        """切换当前激活的 Provider。"""
        data = await ProviderFactory.load_providers(db)
        exists = any(p.get("id") == provider_id for p in data.get("providers", []))
        if not exists:
            raise ValueError(f"Provider ({provider_id}) 不存在")

        data["active_provider_id"] = provider_id

        svc = SystemService(db)
        await svc.upsert_config_item(
            category=ProviderFactory.PROVIDERS_CONFIG_KEY,
            key=ProviderFactory.PROVIDERS_CONFIG_VALUE_KEY,
            value=data,
        )
        return ProviderFactory.list_providers(db)

    # ── 工具 ──

    @staticmethod
    def _encrypt(text: str) -> str:
        """加密敏感字段（占位，实际复用 security.py）。"""
        # TODO: 复用 app/core/security.py 的加密函数
        from app.core.security import encrypt_api_key
        return encrypt_api_key(text)

    @staticmethod
    async def migrate_from_env(db: AsyncSession):
        """启动时从环境变量迁移默认 Provider 配置到 DB。"""
        data = await ProviderFactory.load_providers(db)
        if data.get("providers"):
            return  # 已有配置，跳过迁移

        if settings.LLM_API_KEY:
            provider = {
                "id": f"provider-{uuid.uuid4().hex[:12]}",
                "type": "openai_compatible",
                "name": f"默认 ({settings.LLM_MODEL})",
                "enabled": True,
                "config": {
                    "api_key": ProviderFactory._encrypt(settings.LLM_API_KEY),
                    "base_url": settings.LLM_BASE_URL,
                    "model": settings.LLM_MODEL,
                    "temperature": settings.LLM_TEMPERATURE,
                    "max_tokens": settings.LLM_MAX_TOKENS,
                    "embedding_model": settings.EMBEDDING_MODEL,
                    "embedding_dimension": settings.EMBEDDING_DIMENSION,
                },
            }
            data = {
                "active_provider_id": provider["id"],
                "providers": [provider],
            }
        else:
            data = {"active_provider_id": None, "providers": []}

        svc = SystemService(db)
        await svc.upsert_config_item(
            category=ProviderFactory.PROVIDERS_CONFIG_KEY,
            key=ProviderFactory.PROVIDERS_CONFIG_VALUE_KEY,
            value=data,
        )
        logger.info("AI Provider 配置已从环境变量迁移到 DB")
```

### 5.2 修改 `app/services/llm_provider.py`

新增 `OllamaProvider` 类和 `NoopProvider` 降级类：

```python
# 在 llm_provider.py 中新增

class OllamaProvider(LLMProvider):
    """Ollama 本地模型 Provider。

    Ollama 的 Chat API 与 OpenAI 格式不同，需独立实现。
    API 文档: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "http://ollama:11434").rstrip("/")
        self.model = config.get("model", "qwen2.5:7b")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 4096)
        self.embedding_model = config.get("embedding_model", "nomic-embed-text")

    async def chat(self, messages, temperature=None, max_tokens=None):
        """Ollama API: POST /api/chat"""
        import httpx

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]

    async def chat_stream(self, messages, temperature=None, max_tokens=None):
        """Ollama API 流式: POST /api/chat 带 stream=true"""
        import httpx
        import json

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Ollama API: POST /api/embed"""
        import httpx

        payload = {
            "model": self.embedding_model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/api/embed",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("embeddings", [])


class NoopProvider(LLMProvider):
    """无可用 Provider 时的降级响应。"""

    def __init__(self, message: str = "当前未配置 AI Provider"):
        self._message = message

    async def chat(self, messages, temperature=None, max_tokens=None):
        return f"【提示】{self._message}，请前往系统设置添加。"

    async def chat_stream(self, messages, temperature=None, max_tokens=None):
        yield f"【提示】{self._message}，请前往系统设置添加。"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]
```

改造 `OpenAICompatibleProvider` 使其支持从配置字典初始化（而非仅从环境变量）：

```python
class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容接口 Provider。

    支持从 config dict 初始化（DB 配置）或从环境变量加载（向后兼容）。
    """

    def __init__(self, config: Optional[dict] = None):
        if config is not None:
            # 从 DB 配置初始化
            self.api_key = config.get("api_key", "")
            self.base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")
            self.model = config.get("model", "gpt-4o-mini")
            self.embedding_model = config.get("embedding_model", "text-embedding-3-small")
            self.embedding_dimension = config.get("embedding_dimension", 1536)
            self.temperature = config.get("temperature", 0.7)
            self.max_tokens = config.get("max_tokens", 2000)
        else:
            # 从环境变量加载（向后兼容）
            self.api_key = settings.LLM_API_KEY
            self.base_url = settings.LLM_BASE_URL.rstrip("/")
            self.model = settings.LLM_MODEL
            self.embedding_model = settings.EMBEDDING_MODEL
            self.embedding_dimension = settings.EMBEDDING_DIMENSION
            self.temperature = settings.LLM_TEMPERATURE
            self.max_tokens = settings.LLM_MAX_TOKENS
    # ... 其余方法保持不变
```

### 5.3 修改 `app/services/ai_service.py`

将 `get_llm_provider()` 单例替换为 `ProviderFactory.get_active_provider(db)`：

```python
from app.services.provider_factory import ProviderFactory

class AIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._llm: Optional[LLMProvider] = None

    async def _get_llm(self) -> LLMProvider:
        """懒加载当前激活的 Provider（每次调用从 DB 读取）。"""
        return await ProviderFactory.get_active_provider(self.db)

    async def send_message(self, user_id, conversation_id, data):
        # ...
        llm = await self._get_llm()
        reply = await llm.chat(messages)
        # ...

    async def stream_message(self, user_id, conversation_id, data):
        # ...
        llm = await self._get_llm()
        async for chunk in llm.chat_stream(messages):
            yield chunk
        # ...

    async def generate_signal(self, user_id, data):
        # ...
        llm = await self._get_llm()
        reply = await llm.chat(messages)
        # ...

    async def generate_report(self, user_id, data):
        # ...
        llm = await self._get_llm()
        content = await llm.chat(messages)
        # ...
```

### 5.4 新增 API 路由文件：`app/api/v1/ai_providers.py`

```python
"""AI Provider 管理接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.permissions import require_roles
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.provider_factory import ProviderFactory

router = APIRouter(prefix="/ai/providers", tags=["AI Provider 管理"])


@router.get("", summary="获取所有 Provider 配置")
async def list_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有 Provider 配置 + 当前激活的 provider_id。"""
    data = await ProviderFactory.list_providers(db)
    return ApiResponse(data=data)


@router.post("", summary="添加 Provider", status_code=201)
async def add_provider(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")(get_current_user)),
):
    """添加新的 Provider。"""
    try:
        data = await ProviderFactory.add_provider(db, body)
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{provider_id}", summary="删除 Provider")
async def delete_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")(get_current_user)),
):
    """删除 Provider。"""
    try:
        data = await ProviderFactory.delete_provider(db, provider_id)
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{provider_id}/activate", summary="切换当前激活的 Provider")
async def activate_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """切换当前激活的 Provider。"""
    try:
        data = await ProviderFactory.activate_provider(db, provider_id)
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ollama/models", summary="获取 Ollama 可用模型列表")
async def fetch_ollama_models(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """测试连接 Ollama 并获取可用模型列表。"""
    import httpx

    base_url = body.get("base_url", "http://ollama:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return ApiResponse(data={
                "models": [
                    {"name": m["name"], "size": m["size"], "modified_at": m.get("modified_at", "")}
                    for m in models
                ]
            })
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"连接 Ollama 失败: {str(e)}")
```

### 5.5 启动时自动迁移

在 `backend/app/main.py` 的 `_initialize_storage` 函数中，添加 Provider 迁移：

```python
async def _initialize_storage():
    """初始化数据库表、默认用户、AI Provider 配置。"""
    # ... 已有建表逻辑 ...

    # 迁移 AI Provider 配置（从环境变量到 DB）
    async for db in get_db():
        from app.services.provider_factory import ProviderFactory
        await ProviderFactory.migrate_from_env(db)
        break
```

### 5.6 缓存与刷新策略

| 场景                | 行为                                           |
| ------------------- | ---------------------------------------------- |
| 对话时 `_get_llm()` | 每次从 DB 读取当前激活的 Provider，不缓存      |
| 切换 Provider 后    | 下次 `_get_llm()` 自动加载新 Provider          |
| 多实例部署          | 每个实例独立从 DB 读取，切换后自动同步         |
| 无可用 Provider     | `_get_llm()` 返回 `NoopProvider`，提示用户配置 |
| Embedding 降级      | 无 API Key 时返回零向量（不影响系统运行）      |

**为什么不缓存 Provider 实例？**

- 多实例部署时，缓存会导致实例间不一致
- Provider 切换频率极低（天/周级别），性能开销可忽略
- 每次从 DB 读取的代价远小于一次 LLM 调用（毫秒 vs 秒级）

---

## 6. 前端交互设计

### 6.1 系统设置 → AI Provider 管理页（新增 Tab）

在系统设置页面新增 `AI Provider` Tab，位于"用户管理"之后：

```
┌─ 系统设置 ─────────────────────────────────────────┐
│                                                      │
│  [用户管理] [AI Provider] [系统配置] [通知设置] [审计] │
│                                                      │
│ ┌──────────────────────────────────────────────────┐ │
│ │ AI Provider 管理                                  │ │
│ │                                                   │ │
│ │  当前使用的 Provider: [OpenAI GPT-4o ▼]            │ │
│ │                                                   │ │
│ │  ┌─── Provider 列表 ────────────────────────────┐ │ │
│ │  │                                                │ │
│ │  │  ● OpenAI GPT-4o                 激活中       │ │ │
│ │  │    模型: gpt-4o-mini                          │ │ │
│ │  │    接口: https://api.openai.com/v1            │ │ │
│ │  │                                  [编辑] [删除] │ │ │
│ │  │                                                │ │ │
│ │  │  ○ Ollama qwen2.5:7b                          │ │ │
│ │  │    模型: qwen2.5:7b                            │ │ │
│ │  │    接口: http://ollama:11434                   │ │ │
│ │  │                                  [编辑] [删除] │ │ │
│ │  │                                                │ │ │
│ │  │  [+ 添加 Provider]                             │ │ │
│ │  └────────────────────────────────────────────────┘ │ │
│ │                                                   │ │
│ └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### 6.2 添加/编辑 Provider 弹窗

**OpenAI 兼容接口类型：**

```
┌─ 添加 AI Provider ──────────────────────────┐
│                                               │
│  类型:        [OpenAI 兼容接口 ▼]              │
│                                               │
│  名称:        [OpenAI GPT-4o]                 │
│               (自定义标签，方便识别)            │
│                                               │
│  API Key:     [························]      │
│               (编辑时留空不修改)               │
│                                               │
│  接口地址:     [https://api.openai.com/v1]     │
│                                               │
│  模型:        [gpt-4o-mini]                   │
│                                               │
│  Temperature: [0.7  ──────●──────]            │
│                                               │
│  Max Tokens:  [2000]                          │
│                                               │
│  ┌──────────────┐  ┌──────────────┐           │
│  │ 测试连接     │  │ 保存         │           │
│  └──────────────┘  └──────────────┘           │
└───────────────────────────────────────────────┘
```

**Ollama 类型：**

```
┌─ 添加 AI Provider ──────────────────────────┐
│                                               │
│  类型:        [Ollama 本地模型 ▼]              │
│                                               │
│  名称:        [Ollama 本地]                    │
│                                               │
│  接口地址:     [http://ollama:11434]           │
│                                               │
│  模型:        [▼]  ┌───────────────────────┐  │
│              选择模型  │ 刷新模型列表        │  │
│                      │ 正在获取...          │  │
│                      │  ● qwen2.5:7b       │  │
│                      │  ○ llama3.2:3b      │  │
│                      │  ○ nomic-embed-text │  │
│                      └───────────────────────┘  │
│                                               │
│  Temperature: [0.7  ──────●──────]            │
│                                               │
│  Max Tokens:  [4096]                          │
│                                               │
│  ┌──────────────────┐  ┌──────────────┐       │
│  │ 测试并获取模型   │  │ 保存         │       │
│  └──────────────────┘  └──────────────┘       │
└───────────────────────────────────────────────┘
```

### 6.3 AI 对话页的 Provider 提示

```
┌─ AI 助手 ───────────────────────────────────┐
│                                               │
│  当前使用: 【OpenAI GPT-4o】  [切换 ▼]         │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │ 用户: 帮我分析 BTC 走势                  │  │
│  │ 助手: 根据当前技术指标...                │  │
│  │  ⚠️ 免责声明...                         │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  [输入消息...]                     [发送]      │
└───────────────────────────────────────────────┘
```

"切换"下拉菜单列出所有可用 Provider，选中后调用切换 API 即时生效。

### 6.4 前端组件结构

```
frontend/src/pages/system/
├── index.tsx                       # 系统设置主页面（已有 Tab 导航）
├── Users.tsx                       # 用户管理（已有）
├── AIProviders.tsx                 # 【新增】AI Provider 管理页
│   ├── ProviderList.tsx            # Provider 列表 + 激活状态标识
│   ├── ProviderFormModal.tsx       # 添加/编辑弹窗（类型切换表单）
│   ├── OllamaModelFetcher.tsx      # Ollama 模型列表获取器
│   └── ProviderSwitch.tsx          # 切换当前激活 Provider 的下拉框
├── Notifications.tsx               # 通知设置（已有）
├── AuditLog.tsx                    # 操作审计（已有）
└── Config.tsx                      # 系统配置（已有）

frontend/src/api/
├── ai.ts                           # 新增：aiProviderApi
│   ├── getProviders()
│   ├── addProvider(data)
│   ├── deleteProvider(id)
│   ├── activateProvider(id)
│   └── fetchOllamaModels(baseUrl)

frontend/src/types/
├── ai.ts                           # 新增 Provider 类型
│   ├── AIProvider
│   └── OllamaModel
```

---

## 7. Docker 编排（Ollama 部署）

### 7.1 docker-compose.yml 新增 ollama 服务

```yaml
# 在 docker-compose.yml 中新增

  # Ollama 本地大模型服务
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]    # GPU 加速（可选，无 GPU 自动降级 CPU）
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  ollama_data:        # 新增
  pgdata:
  redisdata:
```

### 7.2 首次启动自动拉取模型（初始化容器）

```yaml
# Ollama 模型初始化（仅首次执行）
ollama-pull:
  image: ollama/ollama:latest
  volumes:
    - ollama_data:/root/.ollama
  command: >
    sh -c "
      echo 'Waiting for ollama service...' &&
      sleep 10 &&
      echo 'Pulling deepseek-r1:7b...' &&
      ollama pull deepseek-r1:7b &&
      echo 'Pulling qwen3.5:7b...' &&
      ollama pull qwen3.5:7b &&
      echo 'Pulling nomic-embed-text...' &&
      ollama pull nomic-embed-text &&
      echo 'All models pulled successfully'
    "
  depends_on:
    - ollama
  restart: "no" # 执行完毕即退出
```

### 7.3 后端连接 Ollama 的配置

后端容器通过 Docker 内部网络访问 Ollama，`base_url` 配置为：

```
http://ollama:11434
```

在添加 Ollama Provider 时，前端自动填入此默认地址（可编辑）。

### 7.4 支持模型建议

| 模型               | 大小   | 推荐用途                                | 硬件要求             |
| ------------------ | ------ | --------------------------------------- | -------------------- |
| `deepseek-r1:7b`   | ~4.5GB | 推理/策略优化（**默认安装**）           | 8GB RAM（无 GPU）    |
| `qwen3.5:7b`       | ~4.5GB | 通用对话/市场分析（**默认安装**）       | 8GB RAM（无 GPU）    |
| `deepseek-r1:14b`  | ~9GB   | 高质量推理/策略优化                     | 16GB RAM 或 8GB VRAM |
| `qwen3.5:14b`      | ~9GB   | 高质量分析/策略优化                     | 16GB RAM 或 8GB VRAM |
| `llama3.2:3b`      | ~2GB   | 快速问答/书籍 RAG                       | 4GB RAM              |
| `llama3.2:8b`      | ~4.9GB | 通用对话                                | 8GB RAM              |
| `nomic-embed-text` | ~0.3GB | Embedding（RAG 向量检索，**默认安装**） | 4GB RAM              |

### 7.5 国内镜像加速（可选）

若拉取模型慢，可在 `ollama-pull` 容器中设置环境变量：

```yaml
ollama-pull:
  environment:
    OLLAMA_HOST: "http://ollama:11434"
  # 或使用国内镜像
  command: >
    sh -c "
      ...
      OLLAMA_BASE_URL=https://docker.mirrors.example.com ollama pull qwen2.5:7b
    "
```

---

## 8. API 接口变更清单

### 8.1 新增接口

| 方法     | 路径                                          | 说明                                 | 鉴权       |
| -------- | --------------------------------------------- | ------------------------------------ | ---------- |
| `GET`    | `/api/v1/ai/providers`                        | 获取所有 Provider 配置 + 当前激活 ID | ✅ Trader+ |
| `POST`   | `/api/v1/ai/providers`                        | 添加 Provider                        | ✅ Admin   |
| `DELETE` | `/api/v1/ai/providers/{provider_id}`          | 删除 Provider                        | ✅ Admin   |
| `POST`   | `/api/v1/ai/providers/{provider_id}/activate` | 切换激活                             | ✅ Trader+ |
| `POST`   | `/api/v1/ai/providers/ollama/models`          | 获取 Ollama 可用模型                 | ✅ Trader+ |

### 8.2 修改接口

| 接口                                   | 变更内容                                             |
| -------------------------------------- | ---------------------------------------------------- |
| `POST /ai/conversations/{id}/messages` | 内部调用的 Provider 从环境变量单例切换为 DB 动态配置 |
| `POST /ai/conversations/{id}/stream`   | 同上                                                 |
| `POST /ai/signals/generate`            | 同上                                                 |
| `POST /ai/reports/generate`            | 同上                                                 |

### 8.3 响应格式示例

```jsonc
// GET /api/v1/ai/providers
{
  "code": 0,
  "message": "ok",
  "data": {
    "active_provider_id": "provider-openai-01",
    "providers": [
      {
        "id": "provider-openai-01",
        "type": "openai_compatible",
        "name": "OpenAI GPT-4o",
        "enabled": true,
        "config": {
          "api_key": "****", // 脱敏
          "base_url": "https://api.openai.com/v1",
          "model": "gpt-4o-mini",
          "temperature": 0.7,
          "max_tokens": 2000,
          "embedding_model": "text-embedding-3-small",
          "embedding_dimension": 1536,
        },
        "created_at": "2026-08-14T10:00:00Z",
        "updated_at": "2026-08-14T10:00:00Z",
      },
      {
        "id": "provider-ollama-01",
        "type": "ollama",
        "name": "Ollama 本地",
        "enabled": true,
        "config": {
          "base_url": "http://ollama:11434",
          "model": "qwen3.5:7b",
          "temperature": 0.7,
          "max_tokens": 4096,
          "embedding_model": "nomic-embed-text",
          "embedding_dimension": 768,
        },
        "created_at": "2026-08-14T10:00:00Z",
        "updated_at": "2026-08-14T10:00:00Z",
      },
    ],
  },
}
```

---

## 9. 迁移与兼容性

### 9.1 向后兼容

| 场景                                 | 兼容方案                                                                                                   |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| 已有 `.env` 配置（`LLM_API_KEY` 等） | 启动时自动迁移：若 `system_configs` 中无 `ai/providers` 记录，则从 `.env` 读取并创建一条默认 Provider 配置 |
| 已有 `get_llm_provider()` 调用       | 保留函数，内部改为尝试从 DB 加载；若 DB 无配置则回退到环境变量                                             |
| API 响应格式                         | 新增字段不影响旧前端（旧前端不使用 `ai/providers` 端点）                                                   |

### 9.2 降级策略

| 场景                                | 降级行为                                                      |
| ----------------------------------- | ------------------------------------------------------------- |
| 无任何 Provider 配置                | `_get_llm()` 返回 `NoopProvider`，返回提示消息                |
| `openai_compatible` 的 API Key 无效 | 请求失败，返回 502 错误，前端口头提示"API Key 无效或已过期"   |
| Ollama 服务未启动                   | 请求超时/连接拒绝，返回 502 错误，前端提示"Ollama 服务未启动" |
| 删除当前激活的 Provider             | 接口拒绝（400），前端提示"请先切换到其他 Provider"            |

### 9.3 环境变量变更

`.env.example` 中 LLM 相关配置可保留但标注为**已废弃**，建议用户通过管理页面配置：

```ini
# ========== LLM 配置（已废弃，请通过系统设置页面管理）==========
# 此配置仅用于启动时首次迁移到 DB，迁移后不再生效
# LLM_PROVIDER=openai
# LLM_API_KEY=
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o-mini
```

---

## 10. 风险与应对

| 风险                                                       | 概率 | 影响 | 应对                                                                    |
| ---------------------------------------------------------- | ---- | ---- | ----------------------------------------------------------------------- |
| Ollama 拉取模型体积大（4-9GB），首次启动慢                 | 高   | 中   | 拆分为独立初始化容器，不阻塞主服务；文档提示首次拉取时长                |
| 无 GPU 时 Ollama 推理速度慢（7B 模型 CPU 约 5-10 token/s） | 中   | 中   | 前端流式显示可缓解感知延迟；建议使用小模型（qwen2.5:7b 或 llama3.2:3b） |
| 多个 Provider 切换时，旧会话仍使用旧 Provider              | 低   | 低   | 切换仅影响新消息，历史消息不受影响；可在会话气泡中显示 Provider 名称    |
| API Key 加密存储密钥泄露                                   | 低   | 高   | 使用独立的 `ENCRYPTION_KEY`；密钥从环境变量注入，不存储 DB              |
| 用户删除当前激活的 Provider                                | 低   | 中   | 接口拒绝删除（返回 400 `"请先切换到其他 Provider"`）；前端禁用删除按钮  |
| Ollama 容器 OOM                                            | 中   | 高   | Docker Compose 中设置 `mem_limit`；healthcheck 监控；自动重启策略       |
| 前端无权限用户看到 Provider 配置                           | 低   | 中   | 仅 Admin 可增删改；Trader 可查看和切换                                  |

---

## 11. 实现优先级

| 阶段   | 任务                                               | 预估工时 |
| ------ | -------------------------------------------------- | -------- |
| **P0** | 新增 `OllamaProvider` 类（llm_provider.py）        | 1h       |
| **P0** | 新增 `ProviderFactory` 类（provider_factory.py）   | 2h       |
| **P0** | 改造 `OpenAICompatibleProvider` 支持 config 初始化 | 0.5h     |
| **P0** | 新增 Provider 管理 API 路由（ai_providers.py）     | 2h       |
| **P0** | 修改 `AIService` 改用 `ProviderFactory._get_llm()` | 1h       |
| **P0** | 启动时自动迁移环境变量到 DB                        | 1h       |
| **P1** | docker-compose 新增 ollama 服务                    | 0.5h     |
| **P1** | 前端 AIProvider 管理页面（列表 + 添加/编辑弹窗）   | 4h       |
| **P1** | 前端 AI 对话页 Provider 切换下拉框                 | 1h       |
| **P2** | Ollama 测试连接/获取模型列表功能                   | 1h       |
| **P2** | 审计日志记录 Provider 操作                         | 0.5h     |
| **P2** | 脱敏处理（api_key 响应脱敏）                       | 0.5h     |
| **P3** | 文档更新（.env.example 标注废弃，API 文档）        | 1h       |

---

> 本文档为 AI 模型多 Provider 配置方案的设计稿，实现时请同步更新前端需求文档和后端 API 文档。
