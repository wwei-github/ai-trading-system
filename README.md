# AI 智能交易管理系统

> **AI 驱动的加密货币交易管理平台** — 集成统计分析、AI 策略回测、书籍 RAG 知识库与智能对话，面向个人/小型团队的全栈式交易辅助系统。

---

## 目录

- [功能概览](#功能概览)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
  - [本地开发模式（SQLite）](#本地开发模式sqlite)
  - [Docker 部署模式](#docker-部署模式)
- [配置说明](#配置说明)
  - [运行模式](#运行模式)
  - [LLM / AI 配置](#llm--ai-配置)
  - [数据库配置](#数据库配置)
  - [交易所代理配置](#交易所代理配置)
  - [端口映射](#端口映射)
- [功能模块详解](#功能模块详解)
  - [后端 API 模块](#后端-api-模块)
  - [前端页面](#前端页面)
- [核心功能](#核心功能)
  - [AI 驱动回测](#ai-驱动回测)
  - [书籍 RAG 知识库](#书籍-rag-知识库)
  - [多交易所账号管理](#多交易所账号管理)
  - [AI 智能对话](#ai-智能对话)
- [开发指南](#开发指南)
- [常见问题](#常见问题)
- [免责声明](#免责声明)
- [许可证](#许可证)

---

## 功能概览

| 功能 | 描述 |
|------|------|
| 🚧 **多交易所管理** | TODO — 统一管理 Binance / OKX / Bybit 等交易所账号，支持测试网模式 |
| 🚧 **交易记录** | TODO — 手动录入、自动同步、批量导入导出 |
| 📉 **统计分析** | 盈亏报表、胜率、回撤、夏普比率等核心指标，可视化图表 |
| 🔮 **K 线行情** | 实时行情、K 线图、技术指标（MA/EMA/RSI/MACD/布林带等） |
| 🤖 **AI 策略回测** | LLM 逐根 K 线分析决策，多策略融合，支持预筛优化 |
| 📚 **书籍 RAG** | 上传 PDF/EPUB/TXT，AI 解析构建知识库，语义检索问答 |
| 💬 **AI 智能对话** | 市场分析、策略诊断、风险咨询、书籍问答等多种模式 |
| 📋 **策略管理** | DSL 结构化规则定义，策略模板，融合优化 |
| ⏰ **定时任务** | Celery Beat 定时调度，数据同步、报表生成、风险监控 |
| 🔐 **安全鉴权** | JWT 登录、RBAC 权限、操作审计日志、API 限流 |
| ⚙️ **系统设置** | AI Provider 管理（多模型切换）、系统配置、错误日志 |

---

## 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| **FastAPI 0.110** | 异步 Web 框架，Pydantic v2 校验 |
| **SQLAlchemy 2.0** | 异步 ORM，支持 PostgreSQL / SQLite 自动切换 |
| **Celery 5.3** | 分布式任务队列（AI 回测、书籍解析、数据同步等） |
| **Redis 7** | 缓存 + Celery 消息代理 + SSE 实时推送 |
| **ccxt 4.2** | 统一交易所 API（支持 100+ 交易所） |
| **Alembic** | 数据库迁移管理 |
| **Loguru** | 结构化日志 |

### 前端

| 技术 | 用途 |
|------|------|
| **React 18.3** | UI 框架，函数组件 + Hooks |
| **TypeScript 5.6** | 类型安全 |
| **Ant Design 5.21** | 企业级组件库（中文） |
| **Vite 5.4** | 构建工具，热更新 |
| **Zustand 5** | 轻量状态管理 |
| **@tanstack/react-query 5** | 服务端数据管理 |
| **ECharts 5.5** | 交互式图表 |
| **KLineCharts 9.8** | 专业 K 线图 |

### 基础设施

| 技术 | 用途 |
|------|------|
| **Docker Compose** | 容器编排（6 个服务） |
| **PostgreSQL 15** | 关系型数据库（Docker 模式） |
| **Nginx** | 前端静态资源 + API 反向代理 |
| **tinyproxy** | 交易所 API 代理（大陆环境） |

---

## 目录结构

```
ai-trading-system/
├── backend/                          # Python 后端
│   ├── app/
│   │   ├── api/v1/                   # 路由层（15 个模块）
│   │   ├── core/                     # 配置、数据库引擎、安全、异常
│   │   ├── models/                   # SQLAlchemy 数据模型（~22 个）
│   │   ├── schemas/                  # Pydantic 数据校验
│   │   ├── services/                 # 业务逻辑层（~12 个 Service）
│   │   ├── tasks/                    # Celery 异步任务（6 个模块）
│   │   ├── exchange/                 # 交易所适配器（ccxt 封装）
│   │   ├── middleware/               # 审计日志 / 错误日志
│   │   └── utils/                    # 技术指标、回测引擎、AI 分析
│   ├── alembic/                      # 数据库迁移
│   ├── .env / .env.example           # 环境变量配置
│   └── requirements.txt              # Python 依赖
├── frontend/                         # React 前端
│   ├── src/
│   │   ├── api/                      # API 请求封装（axios）
│   │   ├── components/               # 通用组件（图表/布局/通用）
│   │   ├── pages/                    # 12 个页面
│   │   ├── hooks/                    # 自定义 Hooks（SSE 自动重连等）
│   │   ├── store/                    # Zustand 状态管理
│   │   ├── types/                    # TypeScript 类型定义
│   │   └── styles/                   # 全局样式
│   └── package.json
├── docker/                           # Docker 构建配置
│   ├── Dockerfile.backend            # 后端镜像
│   ├── Dockerfile.frontend           # 前端镜像
│   └── nginx.conf                    # Nginx 配置
├── docker-compose.yml                # 完整容器编排（6 个服务）
├── dev.js                            # 本地一键启动脚本
├── package.json                      # 根目录 npm scripts
└── docs/
    └── system-design.md              # 系统设计文档
```

---

## 快速开始

### 本地开发模式（SQLite）

无需 Docker，零外部依赖，使用 SQLite 数据库 + 内存缓存。

#### 前置要求

- Python 3.10+
- Node.js 18+
- Redis（可选，Celery 需要，AI 回测需要）

#### 1. 配置环境变量

```bash
cd backend
cp .env.example .env
# 编辑 .env，至少设置 LLM_API_KEY
# 确保 RUN_MODE=local（默认）
```

#### 2. 安装依赖

```bash
# 后端
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

#### 3. 启动服务

**方式一：一键启动（推荐）**

```bash
npm run dev
# 或
node dev.js
```

同时启动：
- 后端 API → `http://localhost:8002`
- Celery Worker → 异步任务队列
- Celery Beat → 定时任务调度
- 前端 → `http://localhost:3000`

**方式二：分别启动**

```bash
# 终端 1 - 后端 API
cd backend && uvicorn app.main:app --reload --port 8002

# 终端 2 - Celery Worker（需要 Redis）
cd backend && celery -A app.tasks worker --loglevel=info --concurrency=2

# 终端 3 - Celery Beat（可选）
cd backend && celery -A app.tasks beat --loglevel=info

# 终端 4 - 前端
cd frontend && npm run dev
```

#### 4. 访问

打开浏览器访问 `http://localhost:3000`，系统自动创建默认管理员用户。

---

### Docker 部署模式

使用 PostgreSQL + Redis 生产级配置，适合正式使用。

#### 前置要求

- Docker & Docker Compose
- 大陆用户建议配置代理（见配置说明）

#### 1. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 .env，配置 LLM_API_KEY 等
```

#### 2. 启动

```bash
docker-compose up -d
```

启动 6 个服务：

| 服务 | 容器名 | 说明 |
|------|--------|------|
| **frontend** | Nginx 静态资源 | 前端应用 + API 反代 |
| **backend** | FastAPI | 后端 API 服务 |
| **celery-worker** | Celery Worker | 异步任务处理（4 并发） |
| **celery-beat** | Celery Beat | 定时任务调度 |
| **postgres** | PostgreSQL 15 | 数据库 |
| **redis** | Redis 7 | 缓存 + 消息队列 |
| **proxy** | tinyproxy | 交易所 API 代理 |

#### 3. 访问

打开浏览器访问 `http://localhost:38000`

#### 4. 常用命令

```bash
# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f backend
docker-compose logs -f celery-worker

# 停止
docker-compose down

# 重建镜像（代码变更后）
docker-compose up -d --build

# 清理数据（删除数据库 volume）
docker-compose down -v
```

---

## 配置说明

### 运行模式

系统通过 `RUN_MODE` 环境变量控制运行模式，影响数据库和缓存的选择：

| 模式 | 值 | 数据库 | 缓存 | 适用场景 |
|------|-----|--------|------|---------|
| **local** | `local` | SQLite 文件 | 内存缓存（降级） | 本地开发，零依赖 |
| **docker** | `docker` | PostgreSQL | Redis | Docker Compose 部署 |
| **online** | `online` | PostgreSQL | Redis | 生产环境部署 |

### LLM / AI 配置

API Key 通过环境变量 `LLM_API_KEY` 统一配置，**不在 UI 中填写或展示**。

```bash
# 最小配置（必填）
LLM_API_KEY=sk-xxxxx

# 其他 LLM 配置通过系统设置页面管理（接口地址、模型、Temperature 等）
```

**支持的 Provider 类型：**

- **OpenAI 兼容接口** — 支持 OpenAI、Anthropic、Azure OpenAI 及任何兼容 OpenAI 格式的 API
- **Ollama 本地模型** — 本地运行的开源模型（如 qwen3.5:9b）

> 多 Provider 管理在「系统设置 → AI Provider」页面中操作，配置持久化到数据库。

### 数据库配置

```bash
# local 模式自动使用 SQLite，无需配置
# docker 模式使用 PostgreSQL（docker-compose 自动配置）
DATABASE_URL=postgresql+asyncpg://trading:trading@localhost:15432/trading

# 连接池配置（可选）
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
```

### 交易所代理配置

大陆用户访问 Binance 等境外交易所需配置代理：

```bash
# 本地开发（Clash / V2Ray 等本地代理）
EXCHANGE_PROXY=http://127.0.0.1:7890

# Docker 部署（自动通过 tinyproxy 容器转发，无需手动设置）
# 如需上游代理（用户自有的 Shadowsocks/V2Ray 等）：
PROXY_UPSTREAM=host.docker.internal:7890
```

### 端口映射

| 服务 | local 模式 | Docker 模式 |
|------|-----------|------------|
| 前端 | `3000` | `38000`（Nginx 80） |
| 后端 API | `8002` | `18000`（容器内 8000） |
| PostgreSQL | 无（SQLite） | `15432` |
| Redis | `16379`（可选） | `16379` |
| tinyproxy | 无 | `18888` |

---

## 功能模块详解

### 后端 API 模块

| 路由模块 | 前缀 | 功能 |
|---------|------|------|
| **auth** | `/auth` | 登录、注册、Token 刷新、登出、2FA |
| **users** | `/users` | 用户管理、RBAC 权限 |
| **accounts** | `/accounts` | 🚧 TODO — 交易所账号绑定、加密存储、测试网切换 |
| **trades** | `/trades` | 🚧 TODO — 交易记录 CRUD、同步、导入导出 |
| **trade_tags** | `/trade-tags` | 交易标签管理 |
| **statistics** | `/statistics` | 盈亏统计、核心指标、图表数据 |
| **coins** | `/coins` | 实时行情、K 线、技术指标、自选监控 |
| **strategies** | `/strategies` | 策略定义、DSL 规则、模板 |
| **books** | `/books` | 书籍上传、解析、章节、笔记、RAG 问答 |
| **ai** | `/ai` | AI 对话（5 种模式）、信号、报表 |
| **ai_providers** | `/ai-providers` | AI Provider 配置管理 |
| **ai_backtest_routes** | `/strategies/ai-backtest` | AI 驱动回测 |
| **system** | `/system` | 系统设置、配置管理 |
| **error_log_routes** | `/error-logs` | 错误日志查询 |
| **task_routes** | `/tasks` | 异步任务状态查询 |

### 前端页面

| 路由 | 页面 | 功能 |
|------|------|------|
| `/dashboard` | 📊 仪表盘 | 总览视图 |
| `/accounts` | 🚧 交易所账号 | TODO — 多账号绑定、API Key 管理、测试网 |
| `/trades` | 🚧 交易记录 | TODO — 列表、手动录入、导入导出 |
| `/statistics` | 📈 统计分析 | 盈亏、胜率、回撤、夏普比率、图表 |
| `/coins` | 🔮 币种分析 | 行情、K 线、技术指标、自选 |
| `/strategies` | 🧠 策略管理 | DSL 策略、传统回测、AI 回测 |
| `/books` | 📚 书籍库 | 上传、阅读、笔记、RAG 问答 |
| `/ai` | 🤖 AI 对话 | 多模式 AI 助手 |
| `/prompts` | 📝 Prompt 模板 | 模板管理 |
| `/system` | ⚙️ 系统设置 | 配置、AI Provider、错误日志 |
| `/error-logs` | 🐛 错误日志 | 异常查看 |
| `/tasks` | ⏰ 任务管理 | 异步任务状态 |

---

## 核心功能

### AI 驱动回测

**核心亮点**：使用 LLM 逐根 K 线分析市场行情并做出交易决策，而非传统回测的固定规则引擎。

#### 工作原理

```
K 线数据 → 技术指标计算（indicators.py）
    → 本地模型预筛（可选）→ 判断是否值得深度分析
        → AI 深度分析（LLM）→ 交易决策（买入/卖出/持有）
            → 执行器执行 → 记录交易 → 下一根 K 线
```

#### 特性

- **AI 逐根 K 线分析**：每根 K 线通过 LLM 分析趋势、支撑阻力、形态，生成交易决策
- **双级 AI 过滤优化**：先快速预筛判断是否值得深度分析，再触发 LLM 深度分析（可关闭）
- **多策略融合回测**：最多 5 个策略同时参与回测，综合决策
- **预热数据**：300 根 K 线预热，初始化 AI 分析（趋势、关键位）
- **持仓免分析**：持仓期间暂停 AI 分析，减少 API 调用
- **实时进度推送**：SSE 推送进度，支持随时取消
- **并发控制**：同一用户最多 3 个进行中的回测
- **融合优化**：回测结果融合优化，自动生成新策略

#### 关键技术文件

| 文件 | 用途 |
|------|------|
| `backend/app/services/ai_backtest_service.py` | 业务编排 |
| `backend/app/tasks/ai_backtest_tasks.py` | Celery 异步任务 |
| `backend/app/utils/ai_market_analyzer.py` | AI 市场分析 Prompt |
| `backend/app/utils/decision_executor.py` | 决策执行器 |
| `backend/app/utils/indicators.py` | 技术指标统一计算 |
| `backend/app/utils/local_model_prechecker.py` | 本地模型预筛 |

---

### 书籍 RAG 知识库

上传交易书籍，AI 自动解析构建知识库，支持语义检索问答。

#### 功能流程

```
上传（PDF/EPUB/TXT）→ 异步解析 → 分块处理
    → 向量嵌入 → 知识库构建 → AI 问答
```

#### 特性

- **多格式支持**：PDF、EPUB、TXT，支持扫描版 PDF（OCR）
- **目录结构导航**：自动提取目录，支持树形章节导航
- **笔记/高亮**：章节笔记、高亮标注、书签
- **RAG 语义检索**：向量嵌入 + 余弦相似度，精准定位相关内容
- **跨书联合问答**：同时检索多本书，综合回答并标注来源
- **多轮对话**：保持会话上下文，连续追问
- **知识提取**：从书籍自动提取交易策略规则

---

### 🚧 多交易所账号管理（TODO）

> 该功能尚在开发中，以下为计划中的设计。

基于 CCXT 库，支持 100+ 交易所的统一管理。

#### 支持的交易所

Binance、OKX、Bybit、Coinbase、Gate.io、Kraken、KuCoin、Bitget、MEXC、Huobi 等（CCXT 支持的所有交易所）。

#### 特性

- 现货和合约支持
- 测试网模式（sandbox）
- API Key AES-256 加密存储
- 代理支持（大陆环境）
- 中文错误提示
- 自动限流

---

### AI 智能对话

提供 5 种 AI 对话模式：

| 模式 | 适用场景 |
|------|---------|
| **市场分析** | 分析当前市场行情、趋势判断 |
| **交易策略** | 策略设计、优化建议 |
| **风险诊断** | 持仓风险评估、止损建议 |
| **书籍问答** | 基于已上传书籍的知识问答 |
| **通用对话** | 常规 AI 助手 |

---

## 开发指南

### Git 提交规范

```bash
# 使用中文描述，feat/fix/chore 前缀
feat: 新增 AI 回测预筛开关
fix: 修复 SSE 连接重连失败问题
chore: 更新依赖版本
```

### 代码风格

- **Python**：FastAPI 异步风格，Service 层封装业务逻辑
- **TypeScript**：函数组件 + Hooks，类型定义在 `types/` 中
- **注释**：中英文均可，中文注释优先

### 数据库迁移

```bash
# 自动生成迁移（模型变更后）
cd backend && alembic revision --autogenerate -m "描述"

# 执行迁移
cd backend && alembic upgrade head
```

### 常用命令

```bash
# 后端开发
cd backend && uvicorn app.main:app --reload --port 8002

# 数据库迁移
cd backend && alembic upgrade head

# 前端开发
cd frontend && npm run dev

# 前端构建
cd frontend && npm run build

# Docker 部署
docker-compose up -d --build
docker-compose logs -f backend
```

---

## 常见问题

### Q: 启动后访问页面空白？

A：检查前端是否成功启动，确保 `http://localhost:3000` 可访问。如使用 Docker，检查 `http://localhost:38000`。

### Q: AI 回测一直卡在"准备中"？

A：检查 Celery Worker 是否正常运行，Redis 是否可连接。查看日志：`docker-compose logs -f celery-worker`。

### Q: 🚧 大陆无法访问交易所 API？（TODO 功能）

A：该功能尚未完成，届时可配置 `EXCHANGE_PROXY` 环境变量指向本地代理（如 `http://127.0.0.1:7890`）。

### Q: 如何切换 AI 模型？

A：在「系统设置 → AI Provider」页面中添加或切换 Provider，支持 OpenAI 兼容接口和 Ollama 本地模型。

### Q: API Key 应该配置在哪里？

A：所有 AI 的 API Key 通过 `LLM_API_KEY` 环境变量配置，**不在 UI 中填写或展示**。其他配置（接口地址、模型等）在系统设置页面中管理。

### Q: 如何重置数据库？

A：Docker 模式：`docker-compose down -v && docker-compose up -d`。Local 模式：删除 `backend/trading.db` 文件后重启。

---

## 免责声明

> ⚠️ **重要提示**

1. **非投资建议**：本系统是一个交易辅助分析工具，**不构成任何投资建议、交易建议或投资决策建议**。所有通过 AI 生成的分析、策略和信号仅供参考，不保证盈利。

2. **风险自负**：加密货币交易具有极高风险，可能导致全部资金损失。使用本系统进行的任何交易决策，均由使用者自行承担全部责任。

3. **AI 局限性**：AI 分析基于历史数据和特定算法，无法预测未来市场走势。历史回测结果不代表未来收益。AI 可能产生错误或不准确的分析结果。

4. **API Key 安全**：用户需自行妥善保管交易所 API Key。建议仅授予必要的权限（如只读权限），并对 API Key 设置提现白名单。

5. **不保证可用性**：本系统按"原样"提供，不保证任何时间的可用性、准确性或完整性。系统可能因第三方服务（交易所 API、LLM API 等）不可用而受到影响。

6. **合规责任**：用户需自行确保使用本系统符合所在国家/地区的法律法规。开发者不对因使用本系统产生的任何法律问题承担责任。

7. **数据安全**：尽管系统对 API Key 等敏感数据进行了加密存储，但无法保证绝对安全。用户应自行评估安全风险。

---

## 许可证

本项目基于 **MIT 许可证** 开放源代码。详见 [LICENSE](LICENSE) 文件。

> 各位开发者可自由使用、修改、分发本项目，但需保留原始版权声明。
> 本软件按"原样"提供，无任何明示或暗示的保证。

---

## 项目状态

该项目处于活跃开发阶段，功能持续迭代中。欢迎提交 Issue 和 Pull Request。

---

## 赞助支持

如果这个项目对你有帮助，欢迎请作者喝杯咖啡 ☕

[![赞助](docs/images/donate.png)](docs/images/donate.png)

---

*AI 智能交易管理系统 — 让交易更智能，而非更冲动。*