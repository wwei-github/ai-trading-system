# 14-AI Provider 管理接口文档

> 模块：AI Provider 多 Provider 管理
> 对齐方案：`docs/backend/03-AI模型多Provider配置方案.md` + `docs/backend/04-AI-Provider后端开发任务.md`
> Base URL：`/api/v1/ai/providers`

---

## 目录

1. [Provider 列表](#1-provider-列表)
2. [添加 Provider](#2-添加-provider)
3. [删除 Provider](#3-删除-provider)
4. [切换激活 Provider](#4-切换激活-provider)
5. [获取 Ollama 模型列表](#5-获取-ollama-模型列表)
6. [数据模型](#6-数据模型)

---

## 1. Provider 列表

```
GET /ai/providers
```

返回所有 Provider 配置，API Key 已脱敏为 `****`。

**鉴权：** Trader+

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "active_provider_id": "provider-a1b2c3d4e5f6",
    "providers": [
      {
        "id": "provider-a1b2c3d4e5f6",
        "type": "openai_compatible",
        "name": "默认 (gpt-4o-mini)",
        "enabled": true,
        "config": {
          "api_key": "****",
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
    ]
  }
}
```

---

## 2. 添加 Provider

```
POST /ai/providers
```

添加新的 Provider 配置。API Key 会自动加密存储到数据库。

**鉴权：** Admin 仅限

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 类型：`openai_compatible` / `ollama` |
| name | string | 是 | 名称（如 `默认 (gpt-4o-mini)`） |
| config | object | 是 | 配置对象（详见下方说明） |

**openai_compatible 类型 config 字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| api_key | string | 是 | - | OpenAI 兼容接口的 API Key（加密存储） |
| base_url | string | 否 | `https://api.openai.com/v1` | 接口地址 |
| model | string | 否 | `gpt-4o-mini` | 对话模型 |
| temperature | number | 否 | `0.7` | 采样温度 (0.0~2.0) |
| max_tokens | int | 否 | `2000` | 单次回复最大 token 数 |
| embedding_model | string | 否 | `text-embedding-3-small` | 嵌入模型 |
| embedding_dimension | int | 否 | `1536` | 向量维度 |

**ollama 类型 config 字段：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| base_url | string | 否 | `http://ollama:11434` | Ollama 服务地址 |
| model | string | 否 | `qwen3.5:7b` | 对话模型 |
| temperature | number | 否 | `0.7` | 采样温度 |
| max_tokens | int | 否 | `4096` | 单次回复最大 token 数 |
| embedding_model | string | 否 | `nomic-embed-text` | 嵌入模型 |

**请求示例：**

```json
{
  "type": "openai_compatible",
  "name": "我的 OpenAI",
  "config": {
    "api_key": "sk-xxxxxxxxxxxx",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 2000,
    "embedding_model": "text-embedding-3-small",
    "embedding_dimension": 1536
  }
}
```

**返回结果：** 同 1.1 的完整结构，HTTP 200。

---

## 3. 删除 Provider

```
DELETE /ai/providers/{provider_id}
```

删除指定的 Provider 配置。

**鉴权：** Admin 仅限

**错误响应：**

| 状态码 | 说明 |
|--------|------|
| 400 | 试图删除当前激活的 Provider（需先切换到其他 Provider） |
| 404 | Provider 不存在 |

**返回结果：** 同 1.1 的完整结构。

---

## 4. 切换激活 Provider

```
POST /ai/providers/{provider_id}/activate
```

将指定 Provider 切换为当前激活状态。切换后，后续 AI 对话将使用新 Provider。

**鉴权：** Trader+

**错误响应：**

| 状态码 | 说明 |
|--------|------|
| 404 | Provider 不存在 |

**返回结果：** 同 1.1 的完整结构。

---

## 5. 获取 Ollama 模型列表

```
POST /ai/providers/ollama/models
```

查询指定 Ollama 服务的可用模型列表。

**鉴权：** Trader+

**请求体：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| base_url | string | 否 | `http://ollama:11434` | Ollama 服务地址 |

**请求示例：**

```json
{
  "base_url": "http://localhost:11434"
}
```

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "models": [
      {
        "name": "qwen3.5:7b",
        "size": 4687432192,
        "modified_at": "2026-08-14T10:00:00Z"
      }
    ]
  }
}
```

**错误响应：**

| 状态码 | 说明 |
|--------|------|
| 502 | 连接 Ollama 服务失败（如服务未运行） |

---

## 6. 数据模型

### 6.1 Provider 配置结构

```json
{
  "id": "provider-a1b2c3d4e5f6",
  "type": "openai_compatible",
  "name": "默认 (gpt-4o-mini)",
  "enabled": true,
  "config": {
    "api_key": "****",
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
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一 ID，格式 `provider-{hex12}` |
| type | string | `openai_compatible` / `ollama` |
| name | string | 显示名称 |
| enabled | bool | 是否启用 |
| config | object | 配置项（响应中 api_key 已脱敏为 `****`） |
| created_at | string | 创建时间 (ISO 8601) |
| updated_at | string | 更新时间 (ISO 8601) |

### 6.2 存储方式

Provider 配置持久化到 `system_configs` 表：

| 字段 | 值 |
|------|------|
| category | `ai` |
| key | `providers` |
| value | 包含 `active_provider_id` 和 `providers[]` 的 JSONB 对象 |

### 6.3 启动迁移

首次启动时，若 `system_configs` 表中无 `ai/providers` 配置，且 `.env` 中配置了 `LLM_API_KEY`，系统会自动将环境变量中的 LLM 配置迁移到 DB，生成一个 `openai_compatible` 类型的 Provider 并设为激活状态。

### 6.4 无 Provider 降级

当 `active_provider_id` 为 `null` 或 `providers[]` 为空时，AI 对话返回降级提示：

> 【提示】当前未配置 AI Provider，请前往系统设置添加。