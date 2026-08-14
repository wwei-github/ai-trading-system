# 07-书籍管理与 RAG 问答接口文档（Stage 7）

> 模块：书籍学习 + RAG 知识检索
> 对齐 PRD：§5.7.1 ~ §5.7.3
> Base URL：`/api/v1/books`

---

## 目录

1. [书籍 CRUD](#1-书籍-crud)
2. [文件上传](#2-文件上传)
3. [阅读进度](#3-阅读进度)
4. [内容解析](#4-内容解析)
5. [重新解析](#5-重新解析)
6. [章节管理](#6-章节管理)
7. [全文搜索](#7-全文搜索)
8. [RAG 问答](#8-rag-问答)
9. [AI 知识提取](#9-ai-知识提取)
10. [AI 书籍分析 + 交易系统生成](#10-ai-书籍分析--交易系统生成)
11. [笔记管理](#11-笔记管理)
12. [数据模型](#12-数据模型)

---

## 1. 书籍 CRUD

### 1.1 获取书籍列表

```
GET /books
```

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "title": "日本蜡烛图技术",
      "author": "史蒂夫·尼森",
      "category": "技术分析",
      "file_type": "pdf",
      "cover_url": null,
      "file_path": "/uploads/books/xxx/xxx.pdf",
      "progress": 0.35,
      "metadata": null,
      "parse_status": "completed",
      "parse_progress": 100,
      "total_chapters": 15,
      "total_chunks": 120,
      "created_at": "2026-08-14T10:00:00Z",
      "updated_at": "2026-08-14T10:00:00Z"
    }
  ]
}
```

### 1.2 创建书籍记录

```
POST /books
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 书名 |
| author | string | 否 | 作者 |
| category | string | 否 | 分类 |
| file_type | string | 否 | 文件类型 |
| cover_url | string | 否 | 封面 URL |
| file_path | string | 否 | 文件路径 |
| metadata | object | 否 | 元数据 |

### 1.3 获取书籍详情

```
GET /books/{book_id}
```

### 1.4 更新书籍信息

```
PATCH /books/{book_id}
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 否 | 书名 |
| author | string | 否 | 作者 |
| category | string | 否 | 分类 |
| cover_url | string | 否 | 封面 URL |
| progress | float | 否 | 阅读进度 (0.0~1.0) |
| metadata | object | 否 | 元数据 |

### 1.5 删除书籍

```
DELETE /books/{book_id}
```

删除书籍及其关联的章节、笔记、知识块和上传文件。

---

## 2. 文件上传

### 2.1 上传书籍文件

```
POST /books/upload
```

**请求格式：** `multipart/form-data`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 书籍文件（pdf / epub / txt） |
| title | string | 否 | 书名（默认使用文件名） |
| author | string | 否 | 作者 |
| category | string | 否 | 分类 |

**限制：**
- 单用户最大书籍数：50 本
- 单文件大小限制：由 `MAX_UPLOAD_SIZE` 配置（默认 50MB）
- 支持格式：pdf / epub / txt

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "uuid",
    "title": "日本蜡烛图技术",
    "file_type": "pdf",
    "parse_status": "pending",
    "parse_progress": 0,
    "total_chapters": 0,
    "total_chunks": 0,
    "progress": 0.0
  }
}
```

---

## 3. 阅读进度

### 3.1 更新阅读进度

```
PATCH /books/{book_id}/progress
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| progress | float | 是 | 阅读进度 (0.0~1.0) |

---

## 4. 内容解析

### 4.1 触发内容解析

```
POST /books/{book_id}/parse
```

触发异步解析任务，流程：
1. 提取文本 + 章节（PyMuPDF 优先，PyPDF2 降级）
2. 按章节切分知识块（1000 字符/块，100 字符重叠）
3. 生成向量嵌入（若配置了 LLM_API_KEY）
4. 写入 `book_chapters` + `knowledge_chunks` 表
5. 更新 `book.parse_status / parse_progress / total_chapters / total_chunks`

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "book_id": "uuid",
    "task_id": "celery-task-id",
    "status": "parsing"
  }
}
```

### 4.2 查询解析进度

```
GET /books/{book_id}/parse/progress
```

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "book_id": "uuid",
    "status": "parsing",
    "progress": 70,
    "total_chapters": 0,
    "total_chunks": 0
  }
}
```

| status 值 | 说明 |
|-----------|------|
| `pending` | 等待解析 |
| `parsing` | 正在解析 |
| `completed` | 解析完成 |
| `failed` | 解析失败 |

---

## 5. 重新解析

### 5.1 重新解析书籍内容

```
POST /books/{book_id}/reparse
```

与 `POST /books/{book_id}/parse` 的区别：
- 显式清除旧章节和知识块数据，确保完全重新生成
- 重置解析进度和统计信息（`total_chapters`、`total_chunks` 归零）
- 适用于解析失败后重试，或需要重新提取章节/知识块的场景

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "book_id": "uuid",
    "task_id": "celery-task-id",
    "status": "parsing",
    "reparse": true
  }
}
```

### 4.3 SSE 解析进度推送（增强）

```
GET /books/{book_id}/parse/stream
```

**替代轮询**，通过 Server-Sent Events 实时推送解析进度。

**事件数据格式：**

```
data: {
  "book_id": "uuid",
  "status": "parsing",
  "progress": 45,
  "stage": "chunking",
  "stage_progress": 70,
  "stage_description": "正在分块处理（第 3/5 章）",
  "total_chapters": 8,
  "total_chunks": 120,
  "parsed_chapters": 3,
  "parsed_chunks": 45,
  "error_message": null
}

data: [DONE]
```

**新增字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `stage` | string | 当前阶段：`file_parsing` / `chunking` / `embedding` / `knowledge` / `done` / `failed` |
| `stage_progress` | int | 当前阶段进度 0-100 |
| `stage_description` | string | 人类可读的阶段描述 |
| `parsed_chapters` | int | 已解析章节数 |
| `parsed_chunks` | int | 已生成知识块数 |
| `error_message` | string | 解析失败时记录错误信息 |

推送由 Redis Pub/Sub 驱动，超时 10 分钟自动断开。超时断开后前端可回退到轮询方式。

---

## 6. 章节管理

### 6.1 获取书籍目录

```
GET /books/{book_id}/chapters?include_content=false&page=1&page_size=20
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| include_content | boolean | 否 | 是否包含正文（默认 false，仅返回目录） |
| page | int | 否 | 页码（默认 1，≥1） |
| page_size | int | 否 | 每页条数（默认 20，范围 1~100） |

**返回结果（分页模式）：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "第一章 蜡烛图基础",
        "chapter_order": 1,
        "page_start": 1,
        "page_end": 25,
        "char_count": 8500,
        "level": 1
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20
  }
}
```

**返回结果（含正文模式）：**

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "uuid",
      "book_id": "uuid",
      "title": "第一章 蜡烛图基础",
      "chapter_order": 1,
      "content": "正文内容...",
      "page_start": 1,
      "page_end": 25,
      "char_count": 8500,
      "level": 1
    }
  ]
}
```

### 6.2 获取章节详情

```
GET /books/{book_id}/chapters/{chapter_order}
```

返回指定章节的完整正文。

---

## 7. 全文搜索

### 7.1 书籍全文搜索

```
POST /books/{book_id}/search
```

在书籍知识块中进行 ILIKE 模糊匹配，返回关键词上下文片段。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |
| limit | int | 否 | 返回结果数（默认 20，最大 100） |

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "chunk_id": "uuid",
      "chapter_order": 3,
      "content": "...锤子线是一种重要的反转信号...",
      "score": 1.0,
      "metadata": {
        "chunk_index": 5,
        "char_start": 200,
        "char_end": 1200,
        "chapter_order": 3
      }
    }
  ]
}
```

---

## 8. RAG 问答

### 8.1 书籍 RAG 问答

```
POST /books/{book_id}/qa
```

基于余弦相似度向量检索相关知识片段，结合 LLM 生成回答。

**前置条件：** 书籍 `parse_status` 必须为 `completed`。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| question | string | 是 | 问题内容 |
| top_k | int | 否 | 检索的知识块数量（默认 5，范围 1~20） |

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "answer": "根据书中内容，锤子线是一种重要的底部反转信号[片段 1]...",
    "sources": [
      {
        "chunk_id": "uuid",
        "chapter_order": 3,
        "content": "锤子线的特征是...",
        "score": 0.8923,
        "metadata": {
          "chunk_index": 5,
          "chapter_order": 3
        }
      }
    ]
  }
}
```

**检索策略：**
1. **向量检索（优先）**：若配置了 `LLM_API_KEY`，使用 embedding 向量计算余弦相似度
2. **关键词匹配（降级）**：未配置 API Key 或向量检索失败时，使用关键词重叠度匹配

---

## 9. AI 知识提取

### 9.1 提取交易策略知识

```
POST /books/{book_id}/extract
```

从书籍章节中提取交易策略知识，生成 6 部分结构化策略草稿。

**前置条件：** 书籍 `parse_status` 必须为 `completed`。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chapter_order | int | 否 | 指定章节序号（留空则全书向量检索相关内容） |
| context_chunks | int | 否 | 上下文知识块数量（默认 5，范围 1~20） |

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "entry_rules": "当快线上穿慢线（金叉）且成交量放大时入场做多...",
    "exit_rules": "当快线下穿慢线（死叉）或触及止盈目标时平仓...",
    "sizing": "每笔交易风险不超过总资金的 2%，初始仓位 10%...",
    "risk_control": "止损设在近期低点下方 3%，最大回撤 20%...",
    "applicability": "适用于趋势行情中的 BTC/USDT 1H 周期...",
    "notes": "该策略在震荡市中表现不佳，建议结合 ATR 过滤...",
    "draft_strategy": {
      "name": "AI 提取策略草稿",
      "description": "适用于趋势行情中的 BTC/USDT 1H 周期",
      "symbol": "BTC/USDT",
      "timeframe": "1h",
      "entry_rules": [
        {
          "logic": "AND",
          "conditions": [
            {
              "indicator": "price",
              "operator": "custom",
              "value": "当快线上穿慢线...",
              "description": "由 AI 从书籍中提取的入场规则"
            }
          ]
        }
      ],
      "exit_rules": [ /* 同结构 */ ],
      "position_sizing": {
        "method": "fixed_fraction",
        "fraction": 0.1,
        "description": "每笔交易风险不超过..."
      },
      "risk_control": {
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.15,
        "max_drawdown_pct": 0.2,
        "description": "止损设在近期低点下方 3%..."
      }
    },
    "source_chapters": [3, 5, 7]
  }
}
```

**6 部分策略草稿说明：**

| 部分 | 字段 | 说明 |
|------|------|------|
| 入场规则 | `entry_rules` | 入场条件、信号、指标阈值 |
| 出场规则 | `exit_rules` | 止盈、平仓、退出信号 |
| 仓位管理 | `sizing` | 资金分配、加仓减仓、风险敞口 |
| 风控规则 | `risk_control` | 止损、最大回撤、单笔风险 |
| 适用场景 | `applicability` | 市场、品种、周期、波动环境 |
| 备注 | `notes` | 其他补充说明 |

`draft_strategy` 字段可直接保存为策略（POST `/strategies`），用户可在策略编辑器中微调。

---

## 10. AI 书籍分析 + 交易系统生成

### 10.1 分析书籍并生成完整交易系统

```
POST /books/{book_id}/analyze
```

用大模型深度分析整本书，并生成一个完整可运行的交易系统。

**前置条件：** 书籍 `parse_status` 必须为 `completed`。

**两步流程：**
1. **书籍分析** — LLM 分析书籍内容（交易哲学、策略框架、适用场景），提取核心概念
2. **交易系统生成** — LLM 根据分析结果生成完整的结构化交易系统 DSL

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| save_strategy | bool | 否 | 是否自动保存为策略（默认 true） |
| strategy_name | string | 否 | 策略名称（留空自动生成） |
| focus_areas | string[] | 否 | 重点关注领域，如 `["趋势跟踪", "风险管理"]` |

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "book_analysis": "## 书籍分析报告\n\n### 核心交易哲学\n本书强调...",
    "core_concepts": ["趋势跟踪", "均值回归", "仓位管理", "风险控制"],
    "trading_system": {
      "name": "双均线趋势跟踪系统",
      "category": "trend",
      "description": "基于快慢均线交叉的趋势跟踪策略",
      "entry_rules": [
        {
          "logic": "AND",
          "conditions": [
            {"indicator": "MA", "operator": ">", "value": "MA20", "description": "快线上穿慢线"},
            {"indicator": "volume", "operator": ">", "value": "MA(volume)*1.5", "description": "成交量放大"}
          ]
        }
      ],
      "exit_rules": [
        {
          "logic": "OR",
          "conditions": [
            {"indicator": "MA", "operator": "<", "value": "MA20", "description": "快线下穿慢线"},
            {"indicator": "price", "operator": "<=", "value": "entry_price*0.95", "description": "止损 -5%"}
          ]
        }
      ],
      "position_sizing": {
        "method": "fixed_fraction",
        "fraction": 0.1,
        "description": "每笔交易投入总资金的 10%"
      },
      "risk_control": {
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.15,
        "max_drawdown_pct": 0.2,
        "description": "止损 5%，止盈 15%，最大回撤 20%"
      },
      "params": {},
      "symbol": "BTC-USDT",
      "timeframe": "1h"
    },
    "system_summary": "基于快慢均线交叉的趋势跟踪策略...",
    "saved_strategy_id": "uuid",
    "source_chapters": [1, 3, 5, 7]
  }
}
```

**返回字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| book_analysis | string | 书籍整体分析报告（Markdown 格式） |
| core_concepts | string[] | LLM 提取的核心交易概念列表 |
| trading_system | object | 完整的结构化交易系统（兼容策略 DSL 格式） |
| system_summary | string | 交易系统摘要 |
| saved_strategy_id | UUID | 保存的策略 ID（若 `save_strategy=true`） |
| source_chapters | int[] | 分析引用的来源章节序号列表 |

---

## 11. 书籍关联策略

### 11.1 获取书籍生成的策略列表

```
GET /books/{book_id}/strategies
```

返回从该书 AI 分析生成的所有策略列表，按创建时间降序排列。

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "uuid",
      "name": "双均线趋势跟踪系统",
      "description": "基于快慢均线交叉的趋势跟踪策略",
      "category": "trend",
      "is_active": true,
      "is_template": false,
      "backtest_count": 1,
      "created_at": "2026-08-14T10:00:00Z",
      "updated_at": "2026-08-14T10:00:00Z",
      "source_book_id": "uuid"
    }
  ]
}
```

---

## 13. 笔记管理

### 13.1 获取笔记列表

```
GET /books/{book_id}/notes
```

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "uuid",
      "book_id": "uuid",
      "user_id": "uuid",
      "chapter": "第三章",
      "chapter_order": 3,
      "note_type": "highlight",
      "content": "锤子线是底部反转的关键信号",
      "highlight_range": {"page": 45, "start": 120, "end": 180},
      "created_at": "2026-08-14T10:00:00Z",
      "updated_at": "2026-08-14T10:00:00Z"
    }
  ]
}
```

### 13.2 创建笔记

```
POST /books/{book_id}/notes
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chapter | string | 否 | 章节标题 |
| chapter_order | int | 否 | 章节序号 |
| note_type | string | 否 | 类型：highlight / note / bookmark（默认 note） |
| content | string | 是 | 笔记内容 |
| highlight_range | object | 否 | 高亮范围 `{"page": 10, "start": 100, "end": 200}` |

### 13.3 更新笔记

```
PATCH /books/notes/{note_id}
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 否 | 笔记内容 |
| note_type | string | 否 | 笔记类型 |

### 13.4 删除笔记

```
DELETE /books/notes/{note_id}
```

---

## 14. 数据模型

### Book（书籍）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 所属用户 |
| title | string(500) | 书名 |
| author | string(200) | 作者 |
| category | string(100) | 分类 |
| file_path | string(1000) | 文件路径 |
| file_type | string(20) | 文件类型：pdf / epub / txt |
| cover_url | string(1000) | 封面 URL |
| progress | float | 阅读进度 (0.0~1.0) |
| metadata | JSONB | 元数据 |
| parse_status | string(20) | 解析状态：pending / parsing / completed / failed |
| parse_progress | int | 解析进度 (0-100) |
| **parse_stage** | string(30) | 当前解析阶段：`file_parsing` / `chunking` / `embedding` / `knowledge` / `done` / `failed` |
| **parse_stage_progress** | int | 当前阶段进度 (0-100) |
| **parse_stage_description** | string(200) | 阶段描述（人类可读） |
| **parse_error_message** | text | 解析失败时记录错误信息 |
| **parsed_chapters** | int | 已解析章节数（进度报告用） |
| **parsed_chunks** | int | 已生成知识块数（进度报告用） |
| total_chapters | int | 总章节数 |
| total_chunks | int | 总知识块数 |
| **strategy_count** | int | 关联策略数（AI分析生成） |

### BookChapter（章节）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| book_id | UUID | 所属书籍（CASCADE 删除） |
| title | string(500) | 章节标题 |
| chapter_order | int | 章节序号（从 1 开始） |
| content | text | 章节正文 |
| page_start | int | 起始页码（PDF） |
| page_end | int | 结束页码 |
| char_count | int | 字符数 |
| level | int | 层级（1=一级，2=二级，3=三级） |

### KnowledgeChunk（知识块）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| book_id | UUID | 所属书籍 |
| chapter_order | int | 所属章节序号 |
| content | text | 文本内容 |
| embedding | text | 向量嵌入（JSON 字符串） |
| metadata | JSONB | 元数据（chunk_index / char_start / char_end / chapter_order） |

### BookNote（笔记）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| book_id | UUID | 所属书籍 |
| user_id | UUID | 所属用户 |
| chapter | string(500) | 章节标题 |
| chapter_order | int | 章节序号 |
| note_type | string(20) | 类型：highlight / note / bookmark |
| content | text | 笔记内容 |
| highlight_range | JSONB | 高亮范围 |
