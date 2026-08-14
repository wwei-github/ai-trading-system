# 04 AI Provider 后端开发任务

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 日期 | 2026-08-14 |
| 前置文档 | [03-AI模型多Provider配置方案.md](./03-AI模型多Provider配置方案.md) |
| 涉及文件 | `backend/app/services/`、`backend/app/api/v1/`、`backend/app/main.py`、`docker-compose.yml` |

---

## 目录

1. [任务概览](#1-任务概览)
2. [P0：核心 Provider 层改造](#2-p0核心-provider-层改造)
3. [P0：ProviderFactory 工厂类](#3-p0providerfactory-工厂类)
4. [P0：Provider 管理 API](#4-p0provider-管理-api)
5. [P0：AIService 改造](#5-p0aiservice-改造)
6. [P0：启动时自动迁移](#6-p0启动时自动迁移)
7. [P1：Docker 编排](#7-p1docker-编排)
8. [P2：安全与审计](#8-p2安全与审计)
9. [P3：收尾清理](#9-p3收尾清理)
10. [验收标准](#10-验收标准)

---

## 1. 任务概览

### 1.1 开发目标

将 AI Provider 配置从 `.env` 环境变量迁移到 `system_configs` 表，支持：
- **多 Provider 管理**：OpenAI 兼容接口（API Key 加密存储）+ Ollama 本地模型
- **运行时切换**：无需重启后端，切换即时生效
- **Docker 部署**：Ollama 容器化部署，自动拉取 `deepseek-r1:7b`、`qwen3.5:7b`、`nomic-embed-text` 三个模型

### 1.2 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| 修改 | `backend/app/services/llm_provider.py` | 新增 `OllamaProvider`、`NoopProvider`；改造 `OpenAICompatibleProvider` 支持 config 初始化 |
| 新增 | `backend/app/services/provider_factory.py` | Provider 工厂：从 DB 读取、创建实例、CRUD 管理 |
| 新增 | `backend/app/api/v1/ai_providers.py` | Provider 管理 REST API |
| 修改 | `backend/app/services/ai_service.py` | 将 `get_llm_provider()` 替换为 `ProviderFactory.get_active_provider(db)` |
| 修改 | `backend/app/main.py` | 启动时调用 `ProviderFactory.migrate_from_env()` |
| 修改 | `docker-compose.yml` | 新增 `ollama` 和 `ollama-pull` 服务 |
| 修改 | `backend/app/core/security.py`（或新增） | 添加 `encrypt_api_key` / `decrypt_api_key` 函数 |
| 修改 | `backend/.env.example` | 标注 LLM 配置为已废弃 |

### 1.3 依赖关系

```
provider_factory.py
  ├── 依赖: system_service.py（已有）、llm_provider.py（修改）
  └── 被依赖: ai_service.py（修改）、ai_providers.py（新增）

ai_providers.py
  ├── 依赖: provider_factory.py（新增）
  └── 注册到: app/main.py 的 router include

OllamaProvider
  └── 依赖: httpx（已有）
```

---

## 2. P0：核心 Provider 层改造

### 2.1 改造 `OpenAICompatibleProvider.__init__`

**文件：** [backend/app/services/llm_provider.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/services/llm_provider.py)

将构造函数改为支持从 `config` 字典初始化，同时保留从环境变量加载的向后兼容路径。

**关键代码：**

```python
class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, config: Optional[dict] = None):
        if config is not None:
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
            ...
```

**验收：**
- [ ] `OpenAICompatibleProvider(config={...})` 从字典初始化正常
- [ ] `OpenAICompatibleProvider()` 无参构造从环境变量加载正常
- [ ] `chat()`、`chat_stream()`、`embed()` 三种方法均可用

### 2.2 新增 `OllamaProvider` 类

在 [llm_provider.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/services/llm_provider.py) 末尾新增。

**API 对照：**

| 功能 | OpenAI | Ollama |
|------|--------|--------|
| Chat 端点 | `POST /v1/chat/completions` | `POST /api/chat` |
| 流式格式 | `data: { choices: [{ delta: { content } }] }` | 每行独立 JSON `{ message: { content }, done: bool }` |
| Embed 端点 | `POST /v1/embeddings` | `POST /api/embed` |
| 认证 | Bearer Token | 无 |

**关键代码：**

```python
class OllamaProvider(LLMProvider):
    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "http://ollama:11434").rstrip("/")
        self.model = config.get("model", "qwen3.5:7b")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 4096)
        self.embedding_model = config.get("embedding_model", "nomic-embed-text")

    async def chat(self, messages, temperature=None, max_tokens=None):
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
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    async def chat_stream(self, messages, temperature=None, max_tokens=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": { ... },
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if data.get("done", False):
                        break

    async def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.embedding_model, "input": texts}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self.base_url}/api/embed", json=payload)
            resp.raise_for_status()
            return resp.json().get("embeddings", [])
```

**验收：**
- [ ] `OllamaProvider` 实例化正常，默认值正确
- [ ] `chat()` 调用正常（需 Ollama 服务运行）
- [ ] `chat_stream()` 流式输出正常
- [ ] `embed()` 向量生成正常

### 2.3 新增 `NoopProvider` 降级类

```python
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

---

## 3. P0：ProviderFactory 工厂类

**新增文件：** [backend/app/services/provider_factory.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/services/provider_factory.py)

### 3.1 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `load_providers(db)` | 从 `system_configs` 加载所有 Provider 配置 | `{ active_provider_id, providers: [] }` |
| `get_active_provider(db)` | 获取当前激活的 Provider 实例 | `LLMProvider` 实例 |
| `list_providers(db)` | 返回脱敏后的 Provider 列表 | `dict` |
| `add_provider(db, data)` | 添加 Provider（加密 API Key） | `dict` |
| `delete_provider(db, id)` | 删除 Provider（禁止删除激活的） | `dict` |
| `activate_provider(db, id)` | 切换当前激活的 Provider | `dict` |
| `migrate_from_env(db)` | 从环境变量迁移默认配置到 DB | `None` |

### 3.2 实现要点

**读取配置：**
```python
@staticmethod
async def load_providers(db: AsyncSession) -> dict:
    svc = SystemService(db)
    config = await svc.get_config_item("ai", "providers")
    if config is None:
        return {"active_provider_id": None, "providers": []}
    return config.value
```

**创建 Provider 实例：**
```python
@staticmethod
def _create_provider(provider_config: dict) -> LLMProvider:
    ptype = provider_config.get("type", "")
    config = provider_config.get("config", {})
    if ptype == "openai_compatible":
        return OpenAICompatibleProvider(config)
    elif ptype == "ollama":
        return OllamaProvider(config)
    return NoopProvider(f"未知的 Provider 类型: {ptype}")
```

**添加 Provider（加密 API Key）：**
```python
@staticmethod
async def add_provider(db: AsyncSession, provider_data: dict) -> dict:
    provider_data["id"] = f"provider-{uuid.uuid4().hex[:12]}"
    provider_data["enabled"] = True
    provider_data["created_at"] = datetime.now(timezone.utc).isoformat()
    provider_data["updated_at"] = provider_data["created_at"]

    config = provider_data.get("config", {})
    if "api_key" in config and config["api_key"]:
        config["api_key"] = encrypt_api_key(config["api_key"])

    svc = SystemService(db)
    data = await ProviderFactory.load_providers(db)
    data["providers"].append(provider_data)
    if not data.get("active_provider_id"):
        data["active_provider_id"] = provider_data["id"]

    await svc.upsert_config_item(category="ai", key="providers", value=data)
    return ProviderFactory.list_providers(db)
```

**删除 Provider（安全检查）：**
```python
@staticmethod
async def delete_provider(db: AsyncSession, provider_id: str) -> dict:
    data = await ProviderFactory.load_providers(db)
    if data.get("active_provider_id") == provider_id:
        raise ValueError("无法删除当前激活的 Provider，请先切换到其他 Provider")
    data["providers"] = [p for p in data["providers"] if p.get("id") != provider_id]
    svc = SystemService(db)
    await svc.upsert_config_item(category="ai", key="providers", value=data)
    return ProviderFactory.list_providers(db)
```

**迁移环境变量：**
```python
@staticmethod
async def migrate_from_env(db: AsyncSession):
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
    else:
        data = {"active_provider_id": None, "providers": []}

    svc = SystemService(db)
    await svc.upsert_config_item(category="ai", key="providers", value=data)
```

**验收：**
- [ ] `load_providers()` 返回正确结构
- [ ] `get_active_provider()` 返回正确的 Provider 实例
- [ ] `add_provider()` 成功添加并加密 API Key
- [ ] `delete_provider()` 禁止删除当前激活的 Provider
- [ ] `activate_provider()` 切换成功
- [ ] `migrate_from_env()` 从环境变量迁移正常

---

## 4. P0：Provider 管理 API

**新增文件：** [backend/app/api/v1/ai_providers.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/api/v1/ai_providers.py)

### 4.1 路由注册

在 `backend/app/main.py` 中注册：

```python
from app.api.v1 import ai_providers
app.include_router(ai_providers.router, prefix="/api/v1")
```

### 4.2 API 路由

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| `GET` | `/api/v1/ai/providers` | Trader+ | 列出所有 Provider（脱敏） |
| `POST` | `/api/v1/ai/providers` | Admin | 添加 Provider |
| `DELETE` | `/api/v1/ai/providers/{provider_id}` | Admin | 删除 Provider |
| `POST` | `/api/v1/ai/providers/{provider_id}/activate` | Trader+ | 切换激活 |
| `POST` | `/api/v1/ai/providers/ollama/models` | Trader+ | 获取 Ollama 模型列表 |

### 4.3 实现要点

**Ollama 模型列表获取：**
```python
@router.post("/ollama/models", summary="获取 Ollama 可用模型列表")
async def fetch_ollama_models(body: dict, db=Depends(get_db), current_user=Depends(get_current_user)):
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

**权限控制：**
```python
from app.core.permissions import require_roles

# 仅 Admin 可增删
current_admin = Depends(require_roles("admin"))
```

**验收：**
- [ ] `GET /api/v1/ai/providers` 返回正确数据结构
- [ ] `POST /api/v1/ai/providers` 添加成功，API Key 加密
- [ ] `DELETE /api/v1/ai/providers/{id}` 删除成功
- [ ] 删除当前激活的 Provider 返回 400 错误
- [ ] `POST /api/v1/ai/providers/{id}/activate` 切换成功
- [ ] `POST /api/v1/ai/providers/ollama/models` 返回模型列表
- [ ] 非 Admin 调用添加/删除接口返回 403

---

## 5. P0：AIService 改造

**文件：** [backend/app/services/ai_service.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/services/ai_service.py)

### 5.1 变更内容

将 `self.llm = get_llm_provider()` 改为每次从 DB 动态加载：

```python
from app.services.provider_factory import ProviderFactory

class AIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # 不再在构造函数中创建 Provider

    async def _get_llm(self) -> LLMProvider:
        """每次调用从 DB 加载当前激活的 Provider。"""
        return await ProviderFactory.get_active_provider(self.db)
```

### 5.2 修改点

需要修改以下方法中的 `self.llm.chat(...)` / `self.llm.chat_stream(...)` 调用：

| 方法 | 行号（当前） | 修改方式 |
|------|-------------|----------|
| `send_message()` | L225 | `llm = await self._get_llm()` → `reply = await llm.chat(messages)` |
| `stream_message()` | L287 | `async for chunk in self.llm.chat_stream(messages)` → 同上 |
| `generate_signal()` | L381 | `reply = await self.llm.chat(messages)` → 同上 |
| `generate_report()` | L511 | `content = await self.llm.chat(messages)` → 同上 |

**验收：**
- [ ] `send_message()` 正常调用当前激活的 Provider
- [ ] `stream_message()` 流式输出正常
- [ ] `generate_signal()` 信号生成正常
- [ ] `generate_report()` 报告生成正常
- [ ] 切换 Provider 后，新消息使用新 Provider

---

## 6. P0：启动时自动迁移

**文件：** [backend/app/main.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/main.py)

### 6.1 在 `_initialize_storage` 中添加迁移

```python
async def _initialize_storage():
    """初始化数据库表、默认用户、AI Provider 配置。"""
    # ... 已有建表和默认用户逻辑 ...

    # 迁移 AI Provider 配置（从环境变量到 DB）
    async for db in get_db():
        from app.services.provider_factory import ProviderFactory
        await ProviderFactory.migrate_from_env(db)
        break
```

**验收：**
- [ ] 首次启动（DB 无 `ai/providers` 配置）时自动从 `.env` 迁移
- [ ] 后续启动不再重复迁移
- [ ] 无 `LLM_API_KEY` 时写入空配置，不报错

---

## 7. P1：Docker 编排

**文件：** [docker-compose.yml](file:///Users/wangwei/Documents/个人项目/ai-trading-system/docker-compose.yml)

### 7.1 新增 ollama 服务

```yaml
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

### 7.2 新增 ollama-pull 初始化容器

```yaml
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
    restart: "no"
```

### 7.3 新增 volume

```yaml
volumes:
  ollama_data:
```

### 7.4 后端连接配置

后端容器内访问 Ollama 的默认地址：`http://ollama:11434`

**验收：**
- [ ] `docker-compose up -d` 后 ollama 服务正常启动
- [ ] ollama-pull 容器执行完毕，模型拉取成功
- [ ] 后端可通过 `http://ollama:11434` 访问 Ollama API
- [ ] `ollama list` 显示 `deepseek-r1:7b`、`qwen3.5:7b`、`nomic-embed-text`

---

## 8. P2：安全与审计

### 8.1 API Key 加密/解密

**文件：** [backend/app/core/security.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/core/security.py)

添加加密函数：

```python
from cryptography.fernet import Fernet
import base64, hashlib

def _derive_fernet_key() -> bytes:
    """从 ENCRYPTION_KEY 派生 Fernet 密钥。"""
    key = settings.ENCRYPTION_KEY.encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(key).digest())

def encrypt_api_key(plain: str) -> str:
    """加密 API Key，返回 base64 字符串。"""
    f = Fernet(_derive_fernet_key())
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")

def decrypt_api_key(encrypted: str) -> str:
    """解密 API Key。"""
    f = Fernet(_derive_fernet_key())
    return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")
```

### 8.2 审计日志

在 `ProviderFactory.add_provider()`、`delete_provider()`、`activate_provider()` 中添加审计日志记录：

```python
from app.models.audit import AuditLog

# 在操作成功后记录
db.add(AuditLog(
    user_id=current_user.id,
    action="create" / "delete" / "update",
    resource_type="ai_provider",
    resource_id=provider_id,
    detail={"provider_name": name, "provider_type": ptype},
))
```

### 8.3 响应脱敏

在 `ProviderFactory.list_providers()` 中，返回前将所有 Provider 的 `api_key` 替换为 `"****"`。

**验收：**
- [ ] API Key 加密存储，解密后与原文一致
- [ ] 响应中 `api_key` 始终为 `"****"`
- [ ] Provider 操作记录到审计日志

---

## 9. P3：收尾清理

### 9.1 更新 `.env.example`

将 LLM 配置部分标注为已废弃：

```ini
# ========== LLM 配置（已废弃，请通过系统设置页面管理）==========
# 此配置仅用于启动时首次迁移到 DB，迁移后不再生效
# LLM_PROVIDER=openai
# LLM_API_KEY=
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o-mini
```

### 9.2 删除无用代码

- 删除 `llm_provider.py` 中的 `_provider` 单例变量和 `get_llm_provider()` 函数（或保留但标注 deprecated）

### 9.3 验证完整性

- [ ] `pytest` 后端测试全部通过
- [ ] `tsc --noEmit` 前端编译无错误
- [ ] `docker-compose up` 整体启动正常

---

## 10. 验收标准

### 10.1 功能验收

| 编号 | 验收项 | 预期结果 |
|------|--------|----------|
| F-01 | 启动后自动迁移 `.env` 配置到 DB | `system_configs` 表有 `ai/providers` 记录 |
| F-02 | 通过 API 添加 OpenAI 兼容 Provider | 添加成功，API Key 加密存储 |
| F-03 | 通过 API 添加 Ollama Provider | 添加成功，无需 API Key |
| F-04 | 切换当前激活的 Provider | 新消息使用新 Provider |
| F-05 | 删除 Provider（非激活的） | 删除成功，列表更新 |
| F-06 | 删除当前激活的 Provider | 返回 400 错误，提示切换 |
| F-07 | 获取 Ollama 模型列表 | 返回 `ollama:11434` 的可用模型 |
| F-08 | 无任何 Provider 时发送消息 | 返回降级提示消息 |
| F-09 | 启动 Ollama 容器 | 自动拉取 3 个模型 |

### 10.2 安全验收

| 编号 | 验收项 | 预期结果 |
|------|--------|----------|
| S-01 | API Key 加密存储 | DB 中 `api_key` 字段为密文 |
| S-02 | API Key 响应脱敏 | 所有 API 响应中 `api_key` 为 `"****"` |
| S-03 | 非 Admin 不可增删 Provider | 返回 403 |
| S-04 | Provider 操作记录审计日志 | `audit_logs` 表有对应记录 |

### 10.3 兼容性验收

| 编号 | 验收项 | 预期结果 |
|------|--------|----------|
| C-01 | 已有 `.env` 配置的旧项目启动正常 | 自动迁移，功能正常 |
| C-02 | 无 `.env` 配置的新项目启动正常 | 写入空配置，降级提示 |
| C-03 | 现有 AI 对话会话不受影响 | 历史消息仍可查看 |

---

> 本文档为后端开发任务清单，按优先级（P0→P3）排列，建议按顺序执行。每个任务完成后对照验收项进行自测。