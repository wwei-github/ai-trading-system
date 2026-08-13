# AI 智能交易管理系统 - 总体设计方案

> 版本：v1.0
> 日期：2026-08-13
> 状态：设计阶段

---

## 一、项目概述

### 1.1 项目定位

构建一套面向个人/小型团队的 **AI 驱动加密货币交易管理系统**，集成多交易所账号管理、交易记录、统计分析、币种分析、交易系统学习与策略执行能力。系统通过 AI 能力辅助用户完成市场分析、策略回测、风险评估与决策支持，形成"数据采集 → 学习研究 → 策略构建 → 模拟验证 → 实盘执行 → 复盘统计"的完整闭环。

### 1.2 核心价值

- **统一管理**：聚合多个交易所账号，统一视图查看资产与交易。
- **数据驱动**：完整的交易记录与多维度统计，量化交易表现。
- **AI 赋能**：结合大模型与量化指标，提供智能分析、信号生成与风险预警。
- **知识沉淀**：通过书籍上传与学习，构建可复用的交易系统知识库。
- **策略闭环**：从交易系统定义、回测、模拟到实盘的全流程支持。

### 1.3 目标用户

- 个人量化交易者 / 加密货币投资者
- 交易策略研究者
- 小型交易团队

---

## 二、需求分析

### 2.1 功能需求（丰富后）

#### 2.1.1 用户与权限管理
- 注册 / 登录 / 登出（邮箱 + 密码，支持 OAuth）
- JWT Token 鉴权，刷新机制
- 角色管理：管理员（Admin）、交易员（Trader）、观察者（Viewer）
- 个人资料、安全设置（二次验证 2FA、登录设备管理）

#### 2.1.2 交易所账号管理
- 多交易所接入：Binance、OKX、Bybit、Huobi、Gate、Coinbase 等（基于 CCXT）
- API Key 加密存储（AES-256 + KMS）
- 账号权限配置：只读 / 交易 / 提币（默认禁用提币）
- 主网 / 测试网切换
- 账号余额实时查询、同步状态监控
- 连接健康检查与异常告警

#### 2.1.3 交易记录管理
- 手动录入交易（现货 / 合约 / 杠杆 / 期权）
- 自动同步交易所历史订单（定时任务 + 手动触发）
- 交易字段：币种、方向、数量、价格、手续费、杠杆、止盈止损、标签、备注
- 交易状态：挂单 / 已成交 / 部分成交 / 已撤单
- 批量导入导出（CSV / Excel）
- 交易关联策略与交易系统

#### 2.1.4 统计分析
- 盈亏统计：日 / 周 / 月 / 年 / 自定义区间
- 核心指标：总盈亏、胜率、盈亏比、平均持仓时长、最大回撤、夏普比率、Sortino 比率
- 资产构成分析（饼图）
- 盈亏分布（柱状图 / 直方图）
- 交易频次与时段分析（热力图）
- 币种贡献度分析
- 自定义仪表盘（拖拽组件）
- 报表导出（PDF / Excel）

#### 2.1.5 币种分析
- 实时行情（WebSocket 推送）
- K 线图（多周期：1m / 5m / 15m / 1h / 4h / 1d / 1w）
- 技术指标：MA / EMA / MACD / RSI / BOLL / KDJ / OBV / ATR
- 多币种对比与相关性矩阵
- AI 智能分析：趋势识别、支撑阻力、形态识别、情绪分析
- 链上数据（可选接入 Glassnode / 链上浏览器）
- 自选币种关注列表

#### 2.1.6 书籍学习系统
- 书籍上传（PDF / EPUB / TXT / DOCX）
- 书籍库管理（分类、标签、作者、封面）
- AI 内容解析：自动提取目录、章节、关键知识点
- 交易系统提取：从书籍中识别交易规则、入场出场条件、风险参数
- 学习进度跟踪、笔记与高亮
- 知识库构建（向量化存储，支持 RAG 检索）
- 与策略模块联动：将书中提取的交易系统一键转化为可回测策略

#### 2.1.7 交易系统（策略）管理
- 交易系统定义：入场规则、出场规则、仓位管理、风险参数
- 策略库管理（创建 / 编辑 / 克隆 / 删除）
- 策略分类：趋势 / 震荡 / 套利 / 网格 / 马丁 / 自定义
- 参数化配置（可视化表单 + JSON 高级模式）
- 历史回测（基于历史 K 线，输出收益曲线、回测指标）
- 模拟交易（Paper Trading，实时行情驱动）
- 实盘交易（绑定交易所账号，风险审核后启动）
- 策略绩效监控与自动止停

#### 2.1.8 AI 能力
- **市场分析助手**：自然语言问答，结合行情与指标给出分析
- **交易信号生成**：基于策略与指标的买卖信号推送
- **风险评估**：持仓风险敞口、波动率预警、爆仓概率
- **策略建议**：根据历史交易表现，AI 建议优化方向
- **报告生成**：自动生成日报 / 周报 / 月报（自然语言总结）
- **情绪分析**：抓取新闻 / 社交媒体，分析市场情绪
- **书籍知识问答**：基于上传书籍的 RAG 问答
- **智能客服**：系统使用帮助与操作引导

### 2.2 非功能需求

| 维度 | 要求 |
|------|------|
| 性能 | API 平均响应 < 300ms；行情推送延迟 < 1s；支撑并发 100+ |
| 可用性 | 系统可用性 ≥ 99.5%；核心交易链路具备熔断与重试 |
| 安全性 | API Key 加密存储；传输 HTTPS；防 SQL 注入 / XSS；操作审计日志 |
| 可扩展 | 模块化设计，支持插件式接入新交易所、新策略、新 AI 模型 |
| 可维护 | 完善日志、监控、告警；CI/CD 自动化部署 |
| 兼容性 | 前端支持 Chrome / Edge / Safari 最新版；响应式适配 |

### 2.3 约束条件
- 默认不开放提币权限，降低资金安全风险。
- 实盘交易需二次确认与风控审核。
- AI 生成内容仅供参考，不构成投资建议（合规免责声明）。

---

## 三、系统架构

### 3.1 总体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端应用 (React)                          │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────────┐  │
│  │ 账号管理  │ 交易记录  │ 统计分析  │ 币种分析  │ 策略/书籍/AI   │  │
│  └──────────┴──────────┴──────────┴──────────┴───────────────┘  │
└──────────────┬──────────────────────────────┬───────────────────┘
               │ HTTPS / WebSocket             │
┌──────────────┴──────────────────────────────┴───────────────────┐
│                      Nginx (反向代理 / 静态资源)                  │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────┴──────────────────────────────────────────────────┐
│                    后端服务 (FastAPI)                             │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────────┐  │
│  │ 用户认证  │ 账号服务  │ 交易服务  │ 分析服务  │ 策略/书籍服务  │  │
│  └──────────┴──────────┴──────────┴──────────┴───────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  AI 服务 (LLM + RAG)                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└──┬────────┬──────────┬───────────┬───────────┬─────────────────┘
   │        │          │           │           │
   ▼        ▼          ▼           ▼           ▼
┌──────┐ ┌──────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
│PostgreSQL│Redis│Celery  │CCXT交易所 │ 向量数据库 │
│(主库) │ │(缓存)│(异步任务)│  (行情/交易) │(Milvus/PG)│
└──────┘ └──────┘ └────────┘ └─────────┘ └──────────┘
```

### 3.2 分层架构

1. **表现层（前端）**：React SPA，负责交互与可视化。
2. **网关层**：Nginx 反向代理、TLS 终止、静态资源、限流。
3. **应用层（后端）**：FastAPI 路由 + 业务服务，按领域划分模块。
4. **AI 层**：LLM 调用、Prompt 管理、RAG 检索、Agent 编排。
5. **数据层**：PostgreSQL（业务数据）、Redis（缓存/队列）、向量库（知识检索）。
6. **集成层**：CCXT 接入交易所，Celery 执行异步任务（同步订单、回测、定时推送）。

### 3.3 关键数据流

- **行情推送**：交易所 WebSocket → 后端 Celery worker → Redis Pub/Sub → 前端 WebSocket。
- **交易下单**：前端 → 后端风控校验 → CCXT → 交易所 → 落库 → 推送结果。
- **策略回测**：前端发起 → Celery 任务 → 加载历史 K 线 → 执行回测引擎 → 结果落库 → 返回报告。
- **AI 问答**：前端 → AI 服务 → RAG 检索知识库 + 拼装 Prompt → LLM → 流式返回。

---

## 四、技术栈

### 4.1 前端技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 框架 | React 18 + TypeScript | 类型安全的组件化开发 |
| 构建 | Vite 5 | 极速冷启动与 HMR |
| UI 库 | Ant Design 5 | 企业级组件库 |
| 状态管理 | Zustand + React Query | 全局状态 + 服务端数据缓存 |
| 路由 | React Router v6 | 嵌套路由与权限路由 |
| HTTP | Axios | 请求拦截、Token 注入 |
| 实时通信 | WebSocket (原生 / socket.io-client) | 行情与通知推送 |
| 图表 | ECharts + klinecharts | 通用图表 + K 线图 |
| 表单 | Ant Design Form + Zod | 表单校验 |
| 工具库 | dayjs / lodash-es / uuid | 时间 / 工具 / 唯一 ID |
| 代码规范 | ESLint + Prettier + Husky | 代码质量保障 |
| 测试 | Vitest + React Testing Library | 单元与组件测试 |

### 4.2 后端技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.11+ | |
| Web 框架 | FastAPI | 高性能异步框架，自动生成 OpenAPI 文档 |
| ASGI 服务器 | Uvicorn / Gunicorn | 生产部署 |
| ORM | SQLAlchemy 2.0 | 异步 ORM |
| 数据库迁移 | Alembic | 版本管理 |
| 主数据库 | PostgreSQL 15 | 业务数据 |
| 缓存/队列 | Redis 7 | 缓存、Pub/Sub、Celery broker |
| 异步任务 | Celery + celery-beat | 定时任务与后台任务 |
| 交易所接入 | CCXT | 统一交易所 API |
| 数据分析 | pandas / numpy | 统计与回测计算 |
| 技术指标 | TA-Lib / pandas-ta | 指标计算 |
| 回测引擎 | 自研 / backtesting.py | 策略回测 |
| AI 编排 | LangChain | LLM 应用编排 |
| LLM | OpenAI / Claude / 本地模型 (Ollama) | 可切换 |
| 向量数据库 | pgvector / Milvus | RAG 知识检索 |
| 文档解析 | PyMuPDF / python-docx | 书籍解析 |
| 鉴权 | python-jose (JWT) + passlib | 认证与加密 |
| 数据校验 | Pydantic v2 | 请求/响应模型 |
| 监控日志 | Loguru + Prometheus + Grafana | 日志与指标监控 |

### 4.3 基础设施

| 类别 | 技术 |
|------|------|
| 容器化 | Docker + Docker Compose |
| 反向代理 | Nginx |
| CI/CD | GitHub Actions |
| 监控 | Prometheus + Grafana |
| 日志聚合 | ELK / Loki |

---

## 五、功能模块设计

### 5.1 模块划分

```
ai-trading-system/
├── frontend/                      # 前端工程
│   ├── src/
│   │   ├── api/                   # 接口封装
│   │   ├── components/            # 通用组件
│   │   ├── layouts/               # 布局
│   │   ├── pages/                 # 页面
│   │   │   ├── dashboard/         # 工作台
│   │   │   ├── accounts/          # 交易所账号
│   │   │   ├── trades/            # 交易记录
│   │   │   ├── statistics/        # 统计分析
│   │   │   ├── coins/             # 币种分析
│   │   │   ├── strategies/        # 交易系统
│   │   │   ├── books/             # 书籍学习
│   │   │   ├── ai/                # AI 助手
│   │   │   └── system/            # 系统设置
│   │   ├── store/                 # 状态管理
│   │   ├── hooks/                 # 自定义 Hook
│   │   ├── utils/                 # 工具函数
│   │   └── types/                 # 类型定义
│   └── ...
│
├── backend/                       # 后端工程
│   ├── app/
│   │   ├── api/                   # 路由层 (v1)
│   │   │   ├── auth.py
│   │   │   ├── accounts.py
│   │   │   ├── trades.py
│   │   │   ├── statistics.py
│   │   │   ├── coins.py
│   │   │   ├── strategies.py
│   │   │   ├── books.py
│   │   │   └── ai.py
│   │   ├── core/                  # 核心配置
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── deps.py
│   │   ├── models/                # 数据库模型
│   │   ├── schemas/               # Pydantic 模型
│   │   ├── services/              # 业务服务
│   │   ├── ai/                    # AI 能力
│   │   │   ├── llm.py
│   │   │   ├── rag.py
│   │   │   ├── prompts.py
│   │   │   └── agents.py
│   │   ├── exchange/              # 交易所封装 (CCXT)
│   │   ├── backtest/              # 回测引擎
│   │   ├── tasks/                 # Celery 任务
│   │   └── utils/
│   ├── tests/
│   └── ...
│
└── docs/                          # 文档
```

### 5.2 模块说明

#### 5.2.1 工作台（Dashboard）
- 资产总览（多账号聚合）
- 今日盈亏、持仓概览
- 关注币种实时行情
- 策略运行状态
- AI 每日简报
- 待办与告警

#### 5.2.2 交易所账号
- 账号列表（状态、余额、权限）
- 新增/编辑/删除账号
- 连接测试
- 余额同步
- 操作日志

#### 5.2.3 交易记录
- 交易列表（筛选、搜索、排序）
- 新增/编辑交易
- 批量导入导出
- 交易详情（关联策略、备注、附件）
- 同步交易所订单

#### 5.2.4 统计分析
- 时间区间选择
- 概览卡片（核心指标）
- 多维图表（盈亏曲线、分布、热力图）
- 币种/策略贡献度
- 自定义仪表盘
- 报表导出

#### 5.2.5 币种分析
- 币种搜索与关注
- K 线图 + 指标叠加
- 技术指标计算与展示
- 多币种对比
- AI 分析报告
- 相关性矩阵

#### 5.2.6 交易系统（策略）
- 策略列表与详情
- 策略编辑器（规则配置 + 参数）
- 回测配置与执行
- 回测结果（收益曲线、指标、交易明细）
- 模拟交易启动/停止
- 实盘交易（风控审核 → 启动 → 监控）
- 策略绩效看板

#### 5.2.7 书籍学习
- 书籍库（网格/列表视图）
- 上传书籍
- 书籍详情（目录、章节、笔记）
- AI 知识提取（交易系统识别）
- 知识库问答
- 学习进度

#### 5.2.8 AI 助手
- 对话式交互界面
- 上下文感知（当前选中币种/策略/交易）
- 多种助手模式：市场分析、策略优化、风险诊断、书籍问答
- 流式输出
- 历史会话管理

#### 5.2.9 系统设置
- 用户管理（管理员）
- 角色权限
- 系统参数（交易所、AI 模型、通知）
- 操作审计
- 通知设置（邮件 / Webhook / 站内信）

---

## 六、数据库设计

### 6.1 核心表结构（PostgreSQL）

#### users（用户）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| email | VARCHAR UNIQUE | 登录邮箱 |
| hashed_password | VARCHAR | 密码哈希 |
| nickname | VARCHAR | 昵称 |
| role | ENUM | admin/trader/viewer |
| is_active | BOOLEAN | |
| totp_secret | VARCHAR | 2FA 密钥 |
| created_at / updated_at | TIMESTAMP | |

#### exchange_accounts（交易所账号）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | FK users | |
| exchange | VARCHAR | binance/okx/... |
| label | VARCHAR | 自定义标签 |
| api_key_encrypted | TEXT | AES 加密 |
| api_secret_encrypted | TEXT | AES 加密 |
| passphrase_encrypted | TEXT | 交易所口令（可选） |
| permissions | JSONB | [read, trade, withdraw] |
| is_testnet | BOOLEAN | |
| status | ENUM | active/disabled/error |
| last_sync_at | TIMESTAMP | |

#### trades（交易记录）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | FK | |
| account_id | FK exchange_accounts | |
| exchange | VARCHAR | |
| symbol | VARCHAR | BTC/USDT |
| market_type | ENUM | spot/futures/swap/margin |
| side | ENUM | buy/sell |
| order_type | ENUM | market/limit/stop/... |
| price | NUMERIC | |
| quantity | NUMERIC | |
| leverage | INT | |
| fee | NUMERIC | |
| fee_currency | VARCHAR | |
| status | ENUM | pending/filled/cancelled/partial |
| strategy_id | FK strategies | 可空 |
| tags | JSONB | |
| note | TEXT | |
| exchange_order_id | VARCHAR | 交易所订单号 |
| executed_at | TIMESTAMP | |
| created_at | TIMESTAMP | |

#### assets_snapshots（资产快照）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | FK | |
| account_id | FK | |
| total_usd | NUMERIC | 折合 USD |
| balances | JSONB | {BTC: {free, used, total}} |
| snapshot_at | TIMESTAMP | |

#### strategies（交易系统/策略）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | FK | |
| name | VARCHAR | |
| category | ENUM | trend/range/arbitrage/grid/martin/custom |
| description | TEXT | |
| rules | JSONB | 入场/出场/仓位/风控规则 |
| params | JSONB | 参数配置 |
| source_book_id | FK books | 可空，来源书籍 |
| status | ENUM | draft/backtesting/paper/live/stopped |
| created_at / updated_at | TIMESTAMP | |

#### backtests（回测记录）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| strategy_id | FK | |
| symbol | VARCHAR | |
| timeframe | VARCHAR | 1h/4h/1d |
| start_date / end_date | DATE | |
| initial_capital | NUMERIC | |
| params | JSONB | |
| result | JSONB | 收益曲线、指标、交易明细 |
| status | ENUM | pending/running/completed/failed |
| created_at | TIMESTAMP | |

#### books（书籍）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | FK | |
| title | VARCHAR | |
| author | VARCHAR | |
| category | VARCHAR | |
| file_path | VARCHAR | 存储路径 |
| file_type | VARCHAR | pdf/epub/... |
| cover_url | VARCHAR | |
| progress | FLOAT | 0-1 |
| metadata | JSONB | 目录、章节 |
| created_at | TIMESTAMP | |

#### book_notes（笔记）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| book_id | FK | |
| user_id | FK | |
| chapter | VARCHAR | |
| content | TEXT | |
| highlight_range | JSONB | |
| created_at | TIMESTAMP | |

#### knowledge_chunks（知识库分块，用于 RAG）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| book_id | FK | |
| content | TEXT | 分块文本 |
| embedding | VECTOR(1536) | pgvector 向量 |
| metadata | JSONB | 章节、页码 |

#### ai_conversations（AI 会话）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | FK | |
| mode | ENUM | market/strategy/risk/book/general |
| title | VARCHAR | |
| context | JSONB | 上下文（币种/策略等） |
| created_at | TIMESTAMP | |

#### ai_messages（AI 消息）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| conversation_id | FK | |
| role | ENUM | user/assistant/system |
| content | TEXT | |
| tokens_used | INT | |
| created_at | TIMESTAMP | |

#### signals（交易信号）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | FK | |
| strategy_id | FK | 可空 |
| symbol | VARCHAR | |
| side | ENUM | buy/sell |
| strength | FLOAT | 信号强度 |
| reason | TEXT | AI/规则依据 |
| created_at | TIMESTAMP | |

#### audit_logs（操作审计）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| user_id | FK | |
| action | VARCHAR | |
| resource_type | VARCHAR | |
| resource_id | VARCHAR | |
| detail | JSONB | |
| ip | VARCHAR | |
| created_at | TIMESTAMP | |

### 6.2 索引策略
- trades: (user_id, executed_at DESC)、(symbol)、(strategy_id)
- assets_snapshots: (user_id, snapshot_at DESC)
- knowledge_chunks: embedding 向量索引 (ivfflat / hnsw)
- ai_messages: (conversation_id, created_at)

---

## 七、API 设计

### 7.1 通用规范
- RESTful 风格，统一前缀 `/api/v1`
- 认证：`Authorization: Bearer <JWT>`
- 响应统一格式：

```json
{
  "code": 0,
  "message": "ok",
  "data": { ... }
}
```

- 错误码：0 成功；4xx 客户端错误；5xx 服务端错误
- 分页：`?page=1&page_size=20`，返回 `total`、`items`
- WebSocket：`/ws/market`（行情）、`/ws/notify`（通知）

### 7.2 主要接口（节选）

#### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /auth/register | 注册 |
| POST | /auth/login | 登录 |
| POST | /auth/refresh | 刷新 Token |
| POST | /auth/logout | 登出 |

#### 交易所账号
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /accounts | 账号列表 |
| POST | /accounts | 新增账号 |
| PUT | /accounts/{id} | 更新账号 |
| DELETE | /accounts/{id} | 删除账号 |
| POST | /accounts/{id}/test | 连接测试 |
| GET | /accounts/{id}/balance | 查询余额 |
| POST | /accounts/{id}/sync | 同步订单 |

#### 交易记录
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /trades | 交易列表（支持筛选） |
| POST | /trades | 新增交易 |
| PUT | /trades/{id} | 更新交易 |
| DELETE | /trades/{id} | 删除交易 |
| POST | /trades/import | 批量导入 |
| GET | /trades/export | 导出 |

#### 统计分析
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /statistics/overview | 概览指标 |
| GET | /statistics/pnl | 盈亏曲线 |
| GET | /statistics/distribution | 盈亏分布 |
| GET | /statistics/heatmap | 时段热力图 |
| GET | /statistics/by-symbol | 币种贡献度 |
| GET | /statistics/report | 生成报表 |

#### 币种分析
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /coins/search | 搜索币种 |
| GET | /coins/{symbol}/kline | K 线数据 |
| GET | /coins/{symbol}/indicators | 技术指标 |
| GET | /coins/{symbol}/ai-analysis | AI 分析 |
| GET | /coins/correlation | 相关性矩阵 |
| WS | /ws/market/{symbol} | 实时行情推送 |

#### 交易系统（策略）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /strategies | 策略列表 |
| POST | /strategies | 创建策略 |
| PUT | /strategies/{id} | 更新策略 |
| DELETE | /strategies/{id} | 删除策略 |
| POST | /strategies/{id}/backtest | 发起回测 |
| GET | /backtests/{id} | 回测结果 |
| POST | /strategies/{id}/paper/start | 启动模拟 |
| POST | /strategies/{id}/paper/stop | 停止模拟 |
| POST | /strategies/{id}/live/start | 启动实盘 |
| POST | /strategies/{id}/live/stop | 停止实盘 |
| GET | /strategies/{id}/performance | 绩效 |

#### 书籍学习
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /books | 书籍列表 |
| POST | /books/upload | 上传书籍 |
| GET | /books/{id} | 书籍详情 |
| DELETE | /books/{id} | 删除 |
| POST | /books/{id}/extract | AI 提取交易系统 |
| GET | /books/{id}/notes | 笔记列表 |
| POST | /books/{id}/notes | 添加笔记 |
| POST | /books/ask | 知识库问答 |

#### AI 助手
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /ai/chat | 对话（支持 SSE 流式） |
| GET | /ai/conversations | 会话列表 |
| GET | /ai/conversations/{id} | 会话详情 |
| POST | /ai/signal | 生成信号 |
| GET | /ai/report/daily | 日报 |

---

## 八、前端架构

### 8.1 页面路由

```
/login                            登录
/dashboard                        工作台
/accounts                         交易所账号
/trades                           交易记录
/trades/new                       新增交易
/statistics                       统计分析
/coins                            币种列表
/coins/:symbol                    币种分析详情
/strategies                       策略列表
/strategies/new                   新建策略
/strategies/:id                   策略详情/回测/模拟/实盘
/books                            书籍库
/books/:id                        书籍详情/学习
/ai                               AI 助手
/system/users                     用户管理
/system/settings                  系统设置
/system/audit                     审计日志
```

### 8.2 状态管理
- **Zustand**：管理全局状态（用户信息、主题、侧边栏折叠、当前账号选择）。
- **React Query**：管理服务端数据（列表、详情），自动缓存与失效。
- **局部状态**：useState / useReducer。

### 8.3 关键组件
- 通用布局（ProLayout 风格：侧边栏 + 顶栏 + 面包屑）
- 权限路由组件（RouteGuard）
- K 线图组件（基于 klinecharts，支持指标叠加）
- 策略规则编辑器（动态表单 + 条件组合）
- AI 对话组件（流式渲染、Markdown 支持）
- 图表组件库（基于 ECharts 封装）
- 实时数据 Hook（useWebSocket）

### 8.4 权限控制
- 路由级：未登录跳转 `/login`；无权限跳转 403。
- 按钮/操作级：基于角色判断显示。
- 数据级：后端按 user_id 隔离数据。

---

## 九、后端架构

### 9.1 分层结构
- **API 层**：路由、参数校验、权限校验、响应封装。
- **Service 层**：核心业务逻辑，事务管理。
- **Model 层**：SQLAlchemy 模型。
- **Schema 层**：Pydantic 请求/响应模型。
- **Exchange 层**：CCXT 封装，统一交易所接口。
- **AI 层**：LLM、RAG、Agent。
- **Task 层**：Celery 异步任务。

### 9.2 异步任务（Celery）
- 定时同步交易所订单与余额
- 定时生成资产快照
- K 线数据下载与缓存
- 策略回测执行
- 模拟交易 / 实盘策略运行（长驻任务）
- AI 报告生成（日报/周报）
- 书籍解析与向量化
- 价格告警与通知推送

### 9.3 交易所接入
- 基于 CCXT 统一封装 `ExchangeClient`，支持同步/异步调用。
- 支持 REST + WebSocket（行情订阅）。
- API Key 解密仅在内存中使用，不落日志。
- 限流与重试机制（按交易所规则）。

### 9.4 回测引擎
- 输入：策略规则、参数、币种、周期、区间、初始资金。
- 流程：加载 K 线 → 逐 Bar 驱动策略 → 模拟成交 → 记录权益曲线。
- 输出：总收益、年化、夏普、最大回撤、胜率、交易明细、收益曲线。
- 支持滑点与手续费模拟。

---

## 十、AI 能力设计

### 10.1 AI 架构

```
┌─────────────────────────────────────────┐
│              AI 服务层                   │
│  ┌──────────┬──────────┬──────────────┐ │
│  │ LLM 适配器│ RAG 检索  │ Agent 编排   │ │
│  └──────────┴──────────┴──────────────┘ │
│  ┌────────────────────────────────────┐ │
│  │     Prompt 模板与管理              │ │
│  └────────────────────────────────────┘ │
└──────┬──────────────┬───────────────────┘
       │              │
       ▼              ▼
┌────────────┐  ┌──────────────┐
│ LLM Provider│  │ 向量数据库    │
│ (OpenAI/    │  │ (pgvector/   │
│  Claude/    │  │  Milvus)     │
│  Ollama)    │  │              │
└────────────┘  └──────────────┘
```

### 10.2 LLM 适配
- 统一 `LLMProvider` 接口，支持切换 OpenAI / Claude / 本地 Ollama。
- 支持流式输出（SSE）。
- Token 用量统计与配额控制。

### 10.3 RAG 知识库
- **数据源**：上传书籍解析后分块、向量化。
- **流程**：用户提问 → 向量检索相关分块 → 拼装上下文 → LLM 生成答案。
- **用途**：书籍问答、策略规则溯源、交易系统知识检索。

### 10.4 Agent 能力
- 市场分析 Agent：调用行情/指标工具，输出分析报告。
- 策略优化 Agent：读取历史交易，给出改进建议。
- 风险诊断 Agent：评估持仓风险，输出预警。
- 报告生成 Agent：定时生成自然语言报告。

### 10.5 Prompt 管理
- 模板版本化管理（存储于数据库或文件）。
- 按场景维护：市场分析、信号生成、风险、报告、书籍问答。
- 支持变量插值与 few-shot 示例。

---

## 十一、安全设计

### 11.1 认证与授权
- JWT（Access Token 短时效 + Refresh Token 长时效）。
- RBAC 角色权限模型。
- 可选 2FA（TOTP）。

### 11.2 敏感数据保护
- API Key/Secret 使用 AES-256 加密存储，密钥由环境变量/KMS 管理。
- 传输全程 HTTPS。
- 敏感字段脱敏展示（仅显示前后若干位）。
- 禁止将解密后的密钥写入日志。

### 11.3 交易安全
- 实盘下单前风控校验：单笔金额上限、日累计上限、最大持仓、最大回撤止停。
- 实盘启动需二次确认（密码 + 2FA）。
- 默认禁用提币权限。
- 关键操作记录审计日志。

### 11.4 应用安全
- 输入校验（Pydantic / Zod）防注入。
- CORS 白名单配置。
- 速率限制（Redis + 慢日志）。
- 文件上传白名单 + 大小限制 + 病毒扫描（可选）。
- 依赖定期扫描（pip-audit / npm audit）。

### 11.5 合规免责
- 系统内显著位置声明：AI 内容仅供参考，不构成投资建议；交易风险自负。

---

## 十二、部署方案

### 12.1 容器化部署（Docker Compose）

```yaml
version: "3.9"
services:
  frontend:
    build: ./frontend
    ports: ["80:80"]
    depends_on: [backend]

  backend:
    build: ./backend
    env_file: .env
    depends_on: [postgres, redis]

  celery-worker:
    build: ./backend
    command: celery -A app.tasks worker -l info
    env_file: .env
    depends_on: [redis, postgres]

  celery-beat:
    build: ./backend
    command: celery -A app.tasks beat -l info
    env_file: .env

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: trading
      POSTGRES_USER: trading
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7
    volumes: ["redisdata:/data"]

  nginx:
    image: nginx:alpine
    ports: ["443:443", "80:80"]
    volumes: ["./nginx.conf:/etc/nginx/nginx.conf"]
    depends_on: [frontend, backend]

volumes:
  pgdata:
  redisdata:
```

### 12.2 环境配置
- 使用 `.env` 管理环境变量（密钥、数据库、AI Key 等）。
- 区分开发 / 测试 / 生产环境。

### 12.3 CI/CD
- GitHub Actions：
  - lint + 单测 + 构建
  - 镜像推送
  - 自动部署到服务器（SSH / Docker Compose）

### 12.4 监控运维
- Prometheus 采集后端指标，Grafana 可视化。
- Loguru 日志落文件 + Loki 聚合。
- 关键告警（交易所连接异常、策略异常停止、AI 用量超限）推送 Webhook/邮件。

---

## 十三、开发计划与里程碑

### 阶段一：基础框架（M1）
- 前后端工程脚手架搭建
- 用户认证与权限
- 基础布局与路由

### 阶段二：核心交易功能（M2）
- 交易所账号管理（CCXT 接入）
- 交易记录录入与同步
- 资产与交易列表展示

### 阶段三：分析与统计（M3）
- 统计分析模块（图表、指标）
- 币种分析（K 线、指标、实时行情）

### 阶段四：策略与回测（M4）
- 交易系统定义与编辑
- 回测引擎
- 模拟交易

### 阶段五：书籍学习与 AI（M5）
- 书籍上传与解析
- RAG 知识库
- AI 助手与各 Agent

### 阶段六：实盘与优化（M6）
- 实盘交易（风控审核）
- AI 报告与信号
- 性能优化、监控、上线

---

## 十四、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 交易所 API 变更 | 接入失效 | CCXT 升级 + 适配层隔离 |
| API Key 泄露 | 资金风险 | 加密存储 + 权限最小化 + 禁用提币 |
| AI 幻觉/误导 | 错误决策 | RAG 溯源 + 免责声明 + 人工确认 |
| 回测过拟合 | 策略失效 | 样本外验证 + 参数敏感性分析 |
| 行情延迟 | 交易滑点 | WebSocket + 本地缓存 + 限流重试 |
| 系统单点 | 可用性下降 | 关键服务多副本 + 数据库备份 |

---

## 十五、附录

### 15.1 术语表
- **交易系统**：一套包含入场、出场、仓位、风控规则的完整策略体系。
- **RAG**：检索增强生成，结合知识库检索与 LLM 生成。
- **Paper Trading**：模拟交易，使用实时行情但不涉及真实资金。
- **CCXT**：统一加密货币交易所 API 库。

### 15.2 参考资料
- FastAPI 官方文档
- Ant Design 官方文档
- CCXT 官方文档
- LangChain 官方文档
- pgvector 文档

---

> 本文档为系统总体设计方案，后续将根据评审反馈迭代细化，并产出接口文档、数据库 DDL、原型设计等补充文档。
