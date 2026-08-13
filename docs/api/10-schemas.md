# 数据模型定义

> 所有请求/响应体中引用的 Schema。

### AIConversationCreate
创建 AI 会话请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| mode | string | 否 | 会话模式：trade_analysis/strategy/book_qa/general/report |
| title | any | 否 | Title |
| context | any | 否 | Context |

### AIMessageCreate
发送 AI 消息请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| content | string | 是 | 消息内容 |
| context | any | 否 | Context |

### AIReportRequest
AI 生成分析报告请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| report_type | string | 否 | 报告类型：trade/strategy/portfolio |
| start_date | any | 否 | Start Date |
| end_date | any | 否 | End Date |
| context | any | 否 | Context |

### AISignalRequest
AI 生成交易信号请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| symbol | string | 是 | 交易对 |
| strategy_id | any | 否 | Strategy Id |
| context | any | 否 | Context |

### BacktestCreate
创建回测请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| strategy_id | string (uuid) | 是 | Strategy Id |
| symbol | string | 是 | Symbol |
| timeframe | string | 否 | Timeframe |
| start_date | string (date) | 是 | Start Date |
| end_date | string (date) | 是 | End Date |
| initial_capital | any | 否 | Initial Capital |
| params | any | 否 | Params |

### Body_upload_book_api_v1_books_upload_post
| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | string (binary) | 是 | 书籍文件 (pdf/epub/txt) |
| title | any | 否 | 书名（可选，默认使用文件名） |
| author | any | 否 | 作者 |
| category | any | 否 | 分类 |

### BookCreate
创建书籍请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| title | string | 是 | 书名 |
| author | any | 否 | Author |
| category | any | 否 | Category |
| file_type | any | 否 | File Type |
| cover_url | any | 否 | Cover Url |
| file_path | any | 否 | File Path |
| metadata | any | 否 | Metadata |

### BookNoteCreate
创建笔记请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| chapter | any | 否 | Chapter |
| content | string | 是 | Content |
| highlight_range | any | 否 | Highlight Range |
| book_id | string (uuid) | 是 | Book Id |

### BookProgressUpdate
阅读进度更新。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| progress | number | 是 | 阅读进度 0.0~1.0 |

### BookQARequest
书籍 RAG 问答请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| question | string | 是 | 问题内容 |
| top_k | integer | 否 | 检索的知识块数量 |

### BookUpdate
更新书籍请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| title | any | 否 | Title |
| author | any | 否 | Author |
| category | any | 否 | Category |
| cover_url | any | 否 | Cover Url |
| progress | any | 否 | Progress |
| metadata | any | 否 | Metadata |

### ExchangeAccountCreate
创建账号请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| exchange | string | 是 | 交易所名称 |
| label | string | 是 | 账号标签 |
| api_key | string | 是 | API Key（明文，传输后加密存储） |
| api_secret | string | 是 | API Secret（明文） |
| passphrase | any | 否 | 口令（OKX 等） |
| permissions | any | 否 | 权限列表 |
| is_testnet | boolean | 否 | 是否为测试网 |

### ExchangeAccountUpdate
更新账号请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| label | any | 否 | Label |
| permissions | any | 否 | Permissions |
| is_testnet | any | 否 | Is Testnet |
| status | any | 否 | Status |

### LiveTradeRequest
实盘交易请求（需二次确认）。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| symbol | string | 是 | Symbol |
| side | string | 是 | Side |
| order_type | string | 否 | Order Type |
| amount | number | 是 | Amount |
| price | any | 否 | Price |
| account_id | string (uuid) | 是 | Account Id |
| confirm | boolean | 否 | 必须为 true 才会执行实盘下单 |

### NotificationSettings
通知设置。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| email_notification | boolean | 否 | Email Notification |
| desktop_notification | boolean | 否 | Desktop Notification |
| trade_signal_alert | boolean | 否 | Trade Signal Alert |
| sync_failure_alert | boolean | 否 | Sync Failure Alert |
| report_frequency | string | 否 | Report Frequency |

### PaperTradeRequest
模拟交易请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| symbol | string | 是 | Symbol |
| side | string | 是 | Side |
| amount | number | 是 | Amount |
| price | any | 否 | Price |

### StrategyCreate
创建策略请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| name | string | 是 | 策略名称 |
| category | string | 是 | 策略类别 |
| description | any | 否 | Description |
| rules | any | 否 | Rules |
| params | any | 否 | Params |
| source_book_id | any | 否 | Source Book Id |

### StrategyUpdate
更新策略请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| name | any | 否 | Name |
| description | any | 否 | Description |
| rules | any | 否 | Rules |
| params | any | 否 | Params |
| status | any | 否 | Status |

### TradeImportItem
批量导入的单条交易记录。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| exchange | string | 是 | Exchange |
| symbol | string | 是 | Symbol |
| market_type | string | 否 | Market Type |
| side | string | 是 | Side |
| order_type | string | 否 | Order Type |
| price | any | 是 | Price |
| quantity | any | 是 | Quantity |
| leverage | any | 否 | Leverage |
| fee | any | 否 | Fee |
| fee_currency | any | 否 | Fee Currency |
| status | string | 否 | Status |
| strategy_id | any | 否 | Strategy Id |
| tags | any | 否 | Tags |
| note | any | 否 | Note |
| exchange_order_id | any | 否 | Exchange Order Id |
| executed_at | string (date-time) | 是 | Executed At |

### TradeImportRequest
批量导入交易记录请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| account_id | string (uuid) | 是 | Account Id |
| trades | Array<[TradeImportItem](./10-schemas.md#TradeImportItem)> | 是 | Trades |

### TradeTagUpdate
交易标签更新。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| tags | Array<string> | 否 | Tags |
| note | any | 否 | Note |

### UserCreate
创建用户请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| email | string | 是 | 邮箱 |
| nickname | string | 是 | 昵称 |
| role | string | 否 | 角色：admin / trader / viewer |
| is_active | boolean | 否 | 是否激活 |

### UserUpdate
更新用户请求。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| email | any | 否 | Email |
| nickname | any | 否 | Nickname |
| role | any | 否 | Role |
| is_active | any | 否 | Is Active |
