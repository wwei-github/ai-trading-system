# API 文档索引

本目录存放后端 HTTP API 文档，内容由 FastAPI OpenAPI schema 自动生成并整理。

**交互文档（需启动后端服务）**
- Swagger UI: <http://localhost:18000/docs>
- ReDoc: <http://localhost:18000/redoc>
- OpenAPI JSON 原始文件：[openapi.json](./openapi.json)

## 文档列表

| # | 文档 | 内容 |
|---|---|---|
| 01 | [01-接口总览.md](./01-接口总览.md) | 模块索引、JWT 鉴权、RBAC 三角色、限流、统一响应、分页、错误码表、审计日志、时区与货币约定 |
| 02 | [02-accounts.md](./02-accounts.md) | 交易所账号：CRUD / 启停 / 连接测试 / 实时余额 / 资产快照 / 支持交易所列表 / 异步同步 |
| 03 | [03-trades.md](./03-trades.md) | 交易记录：多维筛选 + 标签 @> / 全文搜索 / 盈亏重算 / 导入预览确认 / CSV+JSON 流式导出 / 来源只读保护 |
| 04 | [04-statistics.md](./04-statistics.md) | 统计分析接口（待补充） |
| 05 | [05-coins.md](./05-coins.md) | 币种行情接口（待补充） |
| 06 | [06-strategies.md](./06-strategies.md) | 策略管理接口（待补充） |
| 07 | [07-books.md](./07-books.md) | 书籍管理接口（待补充） |
| 08 | [08-ai.md](./08-ai.md) | AI 助手接口（待补充） |
| 09 | [09-system.md](./09-system.md) | 系统管理接口（待补充） |
| 10 | [10-schemas.md](./10-schemas.md) | 请求/响应数据模型（待补充） |
| 11 | [11-trade_tags.md](./11-trade_tags.md) | 交易标签：CRUD + 颜色 + 合并（含源标签替换/删除） |
| 12 | [12-auth.md](./12-auth.md) | 认证鉴权：注册/邮箱验证/登录/登出/refresh/密码找回/TOTP 2FA/登录设备/当前用户 |
| 13 | [13-users.md](./13-users.md) | 用户管理：本人资料/Admin 用户列表与角色变更/重置密码/审计日志（Admin） |

## 刷新文档

当接口定义更新后，重新生成 OpenAPI JSON：

```bash
cd backend
source venv/bin/activate
python -c "import json, os; from app.main import app;   out = os.path.join('..', 'docs', 'api', 'openapi.json');   os.makedirs(os.path.dirname(out), exist_ok=True);   json.dump(app.openapi(), open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)"
```

然后运行本目录的 Markdown 生成脚本（或在 CI 流水线中执行）。
