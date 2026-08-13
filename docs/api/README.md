# API 文档索引

本目录存放后端 HTTP API 文档，内容由 FastAPI OpenAPI schema 自动生成并整理。

**交互文档（需启动后端服务）**
- Swagger UI: <http://localhost:18000/docs>
- ReDoc: <http://localhost:18000/redoc>
- OpenAPI JSON 原始文件：[openapi.json](./openapi.json)

## 文档列表

| # | 文档 | 内容 |
|---|---|---|
| 01 | [01-接口总览.md](./01-接口总览.md) | 模块索引、鉴权、通用响应、分页、错误码 |
| 02 | [02-accounts.md](./02-accounts.md) | 交易所账号接口 |
| 03 | [03-trades.md](./03-trades.md) | 交易记录接口 |
| 04 | [04-statistics.md](./04-statistics.md) | 统计分析接口 |
| 05 | [05-coins.md](./05-coins.md) | 币种分析接口 |
| 06 | [06-strategies.md](./06-strategies.md) | 策略管理接口 |
| 07 | [07-books.md](./07-books.md) | 书籍管理接口 |
| 08 | [08-ai.md](./08-ai.md) | AI 助手接口 |
| 09 | [09-system.md](./09-system.md) | 系统管理接口 |
| 10 | [10-schemas.md](./10-schemas.md) | 请求/响应数据模型 |

## 刷新文档

当接口定义更新后，重新生成 OpenAPI JSON：

```bash
cd backend
source venv/bin/activate
python -c "import json, os; from app.main import app;   out = os.path.join('..', 'docs', 'api', 'openapi.json');   os.makedirs(os.path.dirname(out), exist_ok=True);   json.dump(app.openapi(), open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)"
```

然后运行本目录的 Markdown 生成脚本（或在 CI 流水线中执行）。
