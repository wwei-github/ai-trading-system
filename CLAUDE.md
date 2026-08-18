# AI 智能交易管理系统 (ai-trading-system)

## 项目概览

AI 驱动的全栈交易管理系统，后端 FastAPI + 前端 React (Ant Design)。

- **后端**：FastAPI + SQLAlchemy 2.0（异步） + Celery + ccxt（6 家交易所）
- **前端**：React 18 + Ant Design 5 + Zustand + React Query + ECharts
- **部署**：docker-compose（PostgreSQL + Redis + Celery），也支持 local 模式（SQLite）

## 目录结构

```
.
├── backend/                # Python 后端
│   ├── app/
│   │   ├── api/v1/         # 路由层（14 个模块）
│   │   ├── core/           # 配置（config.py 自动适配 SQLite/PostgreSQL）
│   │   ├── models/         # SQLAlchemy 模型（~20+）
│   │   ├── services/       # 业务逻辑层（~12 个 Service）
│   │   ├── tasks/          # Celery 异步任务
│   │   ├── exchange/       # 交易所适配器（ccxt 封装）
│   │   ├── middleware/      # 审计日志 / 错误日志中间件
│   │   └── utils/          # 工具（indicators/backtest_engine/...）
│   ├── alembic/            # 数据库迁移
│   └── requirements.txt
├── frontend/               # React 前端
│   ├── src/
│   │   ├── api/            # API 请求封装（axios）
│   │   ├── components/     # 通用组件（Chart/Common/Layout）
│   │   ├── hooks/          # useSSE（自动重连）等
│   │   ├── pages/          # 12 个路由页面
│   │   ├── router/         # 路由配置（懒加载）
│   │   ├── store/          # Zustand 状态管理
│   │   ├── types/          # TypeScript 类型
│   │   └── styles/         # 全局样式
│   └── package.json
├── docker/                 # Dockerfile + tinyproxy 配置
├── docker-compose.yml      # 完整部署编排
└── scripts/                # 工具脚本
```

## 运行方式

### 本地开发（SQLite，无需 Docker）

```bash
# 后端
cd backend && uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && npm run dev
```

### Docker 部署

```bash
docker-compose up -d
```

### 端口映射
| 服务 | local | docker |
|------|-------|--------|
| 前端 | 3000 | 38000 |
| 后端 | 8000 | 18000 |
| PostgreSQL | — | 15432 |
| Redis | — | 16379 |

## 技术栈详情

### 后端
- **框架**：FastAPI 0.110 + Pydantic v2 + SQLAlchemy 2.0（异步）
- **数据库**：SQLite（local）/ PostgreSQL（docker/online），Alembic 迁移
- **任务队列**：Celery 5.3（Redis broker）
- **交易所**：ccxt 4.2（Binance/OKX/Bybit/Coinbase/Gate/Huobi）
- **AI/LLM**：OpenAI 兼容接口（支持多 Provider 切换）
- **鉴权**：JWT (python-jose) + passlib(bcrypt) + 2FA(pyotp) + RBAC + 审计日志 + 限流
- **日志**：loguru

### 前端
- **框架**：React 18.3 + TypeScript 5.6 + Vite 5.4
- **UI**：Ant Design 5.21（中文）+ @ant-design/icons
- **状态**：Zustand 5（+ persist 中间件）
- **数据**：@tanstack/react-query 5.59
- **图表**：ECharts 5.5 + KLineCharts 9.8
- **HTTP**：axios（统一拦截器，code !== 0 自动弹错误）

## 关键设计原则

### 响应格式
所有 API 统一返回 `{"code": 0, "message": "ok", "data": ...}`

### RUN_MODE 机制
- `local`：SQLite + 内存代理，零依赖启动
- `docker`：PostgreSQL + Redis + Celery（docker-compose）
- `online`：生产部署

### 配置管理
- 后端 `config.py` 中 `effective_database_url()` 根据 RUN_MODE 自动切换
- 前端 `.env.*.example` 文件管理环境变量，Vite 代理转发 API

### AI 回测（核心功能）
- LLM 驱动策略决策，SSE 推送进度（前端 useSSE 自动重连）
- 多策略独立回测，技术指标通过 `indicators.py` 统一计算
- 后台 Celery 任务管理，支持取消/重试

### 书籍 RAG
- PDF/EPUB 上传 → 解析 → 向量化 → AI 问答
- 支持扫描版 PDF（OCR）

## 开发规范

### Git 提交
- 使用中文描述，feat/fix/chore 前缀
- 单人项目，直接 main 分支开发
- 提交时标注 Co-Authored-By: Claude

### 代码风格
- Python：FastAPI 异步风格，Service 层封装业务逻辑
- TypeScript/React：函数组件 + hooks，类型定义在 `types/` 中
- 代码注释中英文均可，中文注释优先

### 安全注意
- 交易所 API 密钥需加密存储（`ENCRYPTION_KEY`）
- 生产环境必须更换 SECRET_KEY、ENCRYPTION_KEY、JWT_SECRET_KEY
- 交易所 API 需配置代理（大陆环境）

## 常用命令

```bash
# 后端
cd backend && uvicorn app.main:app --reload --port 8000
cd backend && alembic upgrade head

# 前端
cd frontend && npm run dev        # 本地开发
cd frontend && npm run build      # 生产构建

# Docker
docker-compose up -d              # 启动
docker-compose down               # 停止
```

## 项目记忆

项目记忆文件保存在 `~/.claude/projects/.../memory/` 中：
- `project-overview.md` — 项目整体架构
- `backend-tech.md` — 后端技术栈详情
- `frontend-tech.md` — 前端技术栈详情
- `user-profile.md` — 开发者信息
- `skills-and-agents.md` — 建议的 Skill/Agent 配置

## MCP 服务器

配置在 `.claude/settings.json` 中：
| 服务器 | 用途 | 端口 |
|--------|------|------|
| PostgreSQL | 查询数据库、调试数据 | 15432 |
| Redis | 查看 Celery 队列、缓存 | 16379 |
| Docker | 容器管理、日志查看 | — |
| Slack | 交易信号推送（需配置 Token） | — |

## 专用 Agent

定义在 `.claude/agents/` 中：

| Agent | 专注领域 | 关键文件 |
|-------|---------|---------|
| ai-backtest-specialist | AI 回测引擎、LLM 决策、SSE 推送 | ai_backtest_service.py, indicators.py |
| exchange-connector | ccxt 集成、交易所适配、行情同步 | exchange/ 目录 |
| book-rag-pipeline | 书籍解析、RAG 检索、向量嵌入 | book_service.py, book_tasks.py |
| strategy-dsl | 策略 DSL、回测引擎、模拟交易 | strategy_service.py, backtest_engine.py |
| security-audit | JWT 鉴权、RBAC 权限、API 密钥安全 | core/security.py, permissions.py |

## 项目级 Skill

定义在 `.claude/skills/` 中，可通过 `/<skill-name>` 调用：

| Skill | 功能 |
|-------|------|
| `/start-dev` | 本地开发启动（后端 uvicorn + 前端 vite） |
| `/migrate` | 数据库迁移（Alembic 自动生成 + upgrade） |
| `/docker-up` | Docker 构建 + 启动 + 查看日志 |
| `/add-api` | 全链路 API 脚手架模板 |

## 书籍 RAG 改进

### EPUB 目录结构导航
- 优先解析 `toc.ncx` 获取真实目录层级
- 降级解析 `nav.xhtml`（HTML5 Nav 格式）
- 保留章节层级（level 1/2/3）供前端树形展示
- 完全向后兼容，无 TOC 时自动降级为文件名排序

### 多轮对话记忆
- 通过 `session_id` 维持多轮对话上下文
- Redis 存储会话历史（1 小时过期）
- 自动保留最近 5 轮问答
- 通过 `POST /books/{id}/qa/clear` 清除历史

### 跨书联合检索与问答
- `POST /books/cross-qa` 接口，支持同时检索 1-10 本书
- 按相关度排序后，由 LLM 综合回答并标注来源书名
- 支持跨书场景的多轮对话记忆