# 交易记录接口

> **模块前缀**: `/trades` ｜ **RBAC**: Viewer 只读 / Trader & Admin 写操作
> **业务字段数量**: 20 业务字段 + 4 盈亏计算字段 + 2 系统时间戳；手动创建 `source=manual`；导入 `source=import`；同步 `source=exchange_sync`

所有端点需 `Authorization: Bearer <access_token>`。

---

## 1. 端点清单

| # | 方法 | 路径 | 功能 | 权限 |
|---|---|---|---|---|
| 1 | GET | `/trades/health` | 交易模块健康检查 | 登录 |
| 2 | GET | `/trades` | 多维筛选 + 分页查询 | 登录 |
| 3 | POST | `/trades` | 手动创建（source 固定 manual） | Trader / Admin |
| 4 | GET | `/trades/export` | 流式导出（CSV / JSON） | Trader / Admin |
| 5 | POST | `/trades/import/preview` | 导入预览（校验 + 去重） | Trader / Admin |
| 6 | POST | `/trades/import/confirm` | 确认导入（写库，source=import） | Trader / Admin |
| 7 | POST | `/trades/import` | 直接导入（跳过预览，兼容旧客户端） | Trader / Admin |
| 8 | POST | `/trades/recalc` | 盈亏重算 | Trader / Admin |
| 9 | GET | `/trades/{trade_id}` | 详情 | 登录 |
| 10 | PATCH | `/trades/{trade_id}` | 更新（exchange_sync 仅 tags/note/strategy_id） | Trader / Admin |
| 11 | DELETE | `/trades/{trade_id}` | 删除（exchange_sync 禁删） | Trader / Admin |
| 12 | PATCH | `/trades/{trade_id}/tags` | 仅更新标签/备注（所有来源允许） | Trader / Admin |

---

## 2. 公共数据模型

### 2.1 TradeResponse（统一返回）

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "account_id": "uuid",
  "exchange": "binance",
  "symbol": "BTC/USDT",
  "market_type": "spot",
  "side": "sell",
  "order_type": "limit",
  "price": 51000,
  "quantity": 0.1,
  "leverage": null,
  "fee": 5,
  "fee_currency": "USDT",
  "status": "filled",
  "strategy_id": null,
  "tags": ["趋势"],
  "note": "突破卖出",
  "exchange_order_id": null,
  "source": "manual",
  "pnl": 90,
  "pnl_ratio": 0.018,
  "matched_trade_id": "uuid",
  "holding_seconds": null,
  "executed_at": "2026-08-01T14:00:00Z",
  "created_at": "...",
  "updated_at": "..."
}
```

| 分组 | 字段 | 类型 | 说明 |
|---|---|---|---|
| 业务（20 字段） | `exchange` | string | 交易所 |
| | `symbol` | string | 交易对（CCXT 风格，`BTC/USDT`） |
| | `market_type` | enum | `spot` / `futures` / `margin` |
| | `side` | enum | `buy` / `sell` |
| | `order_type` | enum | `market`/`limit`/`stop`/`stop_limit`/`post_only`/`ioc`/`fok` |
| | `price` | Decimal(NUMERIC(20,8)) | 成交价 |
| | `quantity` | Decimal(NUMERIC(20,8)) | 成交数量 |
| | `leverage` | int \| null | 合约杠杆倍数（1~125） |
| | `fee` | Decimal \| null | 手续费 |
| | `fee_currency` | string \| null | 手续费币种 |
| | `status` | enum | `filled`/`partial`/`canceled`/`open` |
| | `strategy_id` | uuid \| null | 关联策略 |
| | `tags` | string[] \| null | 标签（配合 trade_tags 表 + `@>` 查询） |
| | `note` | string \| null | 备注（≤500） |
| | `exchange_order_id` | string \| null | 交易所订单 ID（去重/对账） |
| | `source` | enum | `manual`/`exchange_sync`/`import`/`paper`/`live` |
| | `executed_at` | datetime | 成交时间 |
| | `account_id` | uuid | 所属账号 |
| | `user_id` | uuid | 所属用户 |
| | `id` | uuid | 主键 |
| 盈亏（引擎写入） | `pnl` | Decimal \| null | 已实现盈亏；买入 / 未平仓 null |
| | `pnl_ratio` | Decimal \| null | `pnl / 开仓成本` |
| | `matched_trade_id` | uuid \| null | 配对的买入/开仓 trade_id |
| | `holding_seconds` | int \| null | 持仓时长（秒；平仓时写入） |
| 系统 | `created_at` / `updated_at` | datetime | 自动填充 |

> **盈亏口径对齐 PRD §6.4**：
> - 现货 FIFO 配对：卖出 trade 按执行时间升序匹配买入；撮合成功 `pnl = (sell-buy)*qty - 摊销手续费`。
> - 合约：开仓 trade 仅占位，平仓 trade 按方向反向识别并写入 `pnl`；含杠杆乘数。
> - 未实现盈亏不在 trade 记录（在统计接口按最新快照估算）。

### 2.2 来源只读保护规则

| source | 允许修改字段 | 允许删除 |
|---|---|---|
| `manual` / `import` / `paper` / `live` | 全部（tags/note/price/side...） | ✅ |
| `exchange_sync` | **仅** `tags` / `note` / `strategy_id` | ❌（403） |

Viewer 任何写操作 → 403。

---

## 3. 接口详情

### 3.1 GET `/trades` 多维筛选 + 分页

**查询参数**（全部可选）：

| 参数 | 类型 | 说明 |
|---|---|---|
| `exchange` | string | 交易所 |
| `symbol` | string | 交易对精确匹配 |
| `account_id` | uuid | 账号筛选 |
| `strategy_id` | uuid | 策略筛选 |
| `side` | enum | `buy` / `sell` |
| `status` | enum | `filled` / `partial` / `canceled` / `open` |
| `source` | enum | `manual` / `exchange_sync` / `import` / `paper` / `live` |
| `pnl_status` | enum | `profit`(pnl>0) / `loss`(pnl<0) / `breakeven`(pnl=0) / `unrealized`(pnl=null) |
| `tags` | string[]（重复 query） | 标签包含；Postgres `tags @> ['a','b']`（AND 包含） |
| `search` | string | 全文搜索：`symbol ILIKE %q% OR note ILIKE %q%` |
| `start_date` | datetime | `executed_at >=` |
| `end_date` | datetime | `executed_at <=` |
| `page` | int | 默认 1 |
| `page_size` | int | 默认 20（1~100） |
| `sort_by` | string | `executed_at`(默认) / `price` / `quantity` / `pnl` / `fee` / `created_at` |
| `sort_order` | string | `desc`(默认) / `asc` |

**响应**（PaginatedResponse[TradeResponse]）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total": 2,
    "page": 1,
    "page_size": 20,
    "items": [ TradeResponse, TradeResponse ]
  }
}
```

**示例调用**：

```bash
# 搜索 symbol='BTC/USDT' 且盈利
curl "http://localhost:18000/api/v1/trades?symbol=BTC%2FUSDT&pnl_status=profit" \
  -H "Authorization: Bearer $TOKEN"
```

---

### 3.2 POST `/trades` 手动创建

**请求体 `TradeCreate`**：

| 字段 | 必填 | 类型 |
|---|---|---|
| `account_id` | ✅ | uuid（归属账号；若账号不存在，后续在 service 层抛错） |
| `exchange` | ✅ | string（≤50） |
| `symbol` | ✅ | string（≤30，CCXT 风格 `BTC/USDT`） |
| `market_type` | — | enum；默认 `spot` |
| `side` | ✅ | `buy` / `sell` |
| `order_type` | — | enum；默认 `market` |
| `price` | ✅ | Decimal（>0） |
| `quantity` | ✅ | Decimal（>0） |
| `leverage` | — | int（1~125；合约用） |
| `fee` | — | Decimal（≥0） |
| `fee_currency` | — | string（≤20） |
| `status` | — | enum；默认 `filled` |
| `strategy_id` | — | uuid |
| `tags` | — | string[] |
| `note` | — | string（≤500） |
| `exchange_order_id` | — | string（≤100） |
| `executed_at` | ✅ | datetime（ISO-8601） |

**未验证邮箱限制**：`email_verified=false` 的用户每日最多 10 条 `source=manual` 交易（24:00 UTC 重置）。超量返回 40102。

**盈亏自动触发**：创建后 `recalc_trade(trade.id)` 对同 `symbol` 重算 FIFO / 合约。

**响应**：`TradeResponse`。

---

### 3.3 GET `/trades/export` 流式导出

**查询参数**：与 §3.1 筛选参数相同 + `fmt`。

| 参数 | 类型 | 说明 |
|---|---|---|
| `fmt` | `csv`(默认) / `json` | 导出格式 |

- 导出时忽略 `page` / `page_size`（默认加载 100 条；实际生产建议异步 Celery）。
- CSV 响应：`Content-Type: text/csv; charset=utf-8`；Header 22 列（id → created_at，含盈亏 4 列）。
- JSON 响应：`application/json` 数组（每个元素同 TradeResponse 简化 dict，Decimal 转字符串）。

**示例**：

```bash
# CSV 导出
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:18000/api/v1/trades/export?fmt=csv" \
  -o trades.csv

# JSON 导出
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:18000/api/v1/trades/export?fmt=json" \
  -o trades.json
```

---

### 3.4 POST `/trades/import/preview` 导入预览

**请求体 `TradeImportRequest`**：

```json
{
  "account_id": "uuid",
  "trades": [
    {
      "exchange": "binance",
      "symbol": "BTC/USDT",
      "side": "buy",
      "price": 50000,
      "quantity": 0.1,
      "fee": 5,
      "fee_currency": "USDT",
      "executed_at": "2026-08-01T10:00:00Z"
    }
  ]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `account_id` | ✅ | 归属账号（必须属于当前用户） |
| `trades[].exchange` | ✅ | 交易所 |
| `trades[].symbol` | ✅ | 交易对 |
| `trades[].market_type` | — | 默认 spot |
| `trades[].side` | ✅ | buy/sell |
| `trades[].order_type` | — | 默认 market |
| `trades[].price` | ✅ | >0 |
| `trades[].quantity` | ✅ | >0 |
| `trades[].executed_at` | ✅ | 成交时间（用于去重） |

**去重键**：`account_id + symbol + price ± 1e-8 + quantity ± 1e-8 + executed_at ± 2s`。

**响应 `TradeImportPreviewResponse`**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total": 120,
    "valid": 115,
    "invalid": 2,
    "duplicates": 3,
    "rows": [
      {"row_index": 0, "valid": true,  "duplicate": false},
      {"row_index": 1, "valid": false, "error": "无效的方向: up"},
      {"row_index": 2, "valid": true,  "duplicate": true}
    ]
  }
}
```

- 预览**不写入数据库**，仅用于前端 UI 提示用户确认。

---

### 3.5 POST `/trades/import/confirm` 确认导入

**查询参数**：`skip_duplicates=true|false`（默认 true）。

**请求体**：同 `TradeImportRequest`（推荐直接复用预览时传的那份，保证按相同行序）。

**响应 `TradeImportResponse`**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total": 120,
    "imported": 115,
    "skipped": 5,
    "errors": [
      "第 13 行校验失败: 无效的市场类型",
      "第 44 行导入失败: ..."
    ]
  }
}
```

导入完成后自动 `recalc_all(user_id)`。每条导入 trade 的 `source=import`。

---

### 3.6 POST `/trades/import` 直接导入（兼容）

等同于 `import/confirm` + `skip_duplicates=true` 的快捷路径，**不推荐新前端使用**。

---

### 3.7 POST `/trades/recalc` 盈亏重算

**请求体 `TradeRecalcRequest`**（全部可选）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `trade_ids` | uuid[] | 指定重算的 trade ID 列表；若指定则忽略其他条件 |
| `start_date` | datetime | 限定 executed_at 起点（与 trade_ids 二选一） |
| `end_date` | datetime | 限定终点 |
| `symbol` | string | 仅重算该交易对 |

- `trade_ids` 指定时：逐条 `recalc_trade`（每条会触发同 symbol 全部重算）。
- `trade_ids` 为空时：按条件走 `recalc_all`（FIFO / 合约）。

**响应 `TradeRecalcResponse`**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "recalculated": 2,
    "matched_pairs": 1,
    "errors": []
  }
}
```

| 字段 | 说明 |
|---|---|
| `recalculated` | 被更新（写入 pnl 字段）的 trade 数 |
| `matched_pairs` | 买入 / 开仓 ↔ 卖出 / 平仓的配对次数 |

---

### 3.8 GET `/trades/{trade_id}` 详情

**路径参数**：`trade_id`（uuid）。找不到 → 404。

**响应**：`TradeResponse`。

---

### 3.9 PATCH `/trades/{trade_id}` 更新

**请求体 `TradeUpdate`**（字段均可选）：

| 字段 | 可改场景 |
|---|---|
| `tags` / `note` / `strategy_id` | 所有来源 |
| `exchange`/`symbol`/`market_type`/`side`/`order_type`/`price`/`quantity`/`leverage`/`fee`/`fee_currency`/`status`/`executed_at` | 仅 `source ∈ {manual, import, paper, live}`；exchange_sync 改这些 → 40300 + detail.readonly_fields |

- 若修改了 `price`/`quantity`/`side`/`fee`/`leverage`/`executed_at`，自动触发同 symbol 盈亏重算。
- exchange_sync 来源修改 tags/note 不触发重算。

**响应**：`TradeResponse`；找不到 → 404。

---

### 3.10 DELETE `/trades/{trade_id}` 删除

**规则**：
- `source=exchange_sync` → 403（"交易所同步的交易记录不可删除，请先停用账号同步或删除关联账号"）。
- 找到且允许删 → 200 `{"deleted": true}`。
- 找不到 → 404。

---

### 3.11 PATCH `/trades/{trade_id}/tags` 标签/备注更新

这是 **3.9 的轻量接口**，所有来源均允许（exchange_sync 本身也需给交易打标签）。

**请求体 `TradeTagUpdate`**：

```json
{"tags": ["趋势","网格"], "note": "突破卖出"}
```

两字段均可选（只改 tags 就不传 note）。

---

## 4. 错误示例速查

| 场景 | HTTP | code | message |
|---|---|---|---|
| 枚举值非法（side/order_type/status/...） | 400 | 40000 | 校验错误（含字段名） |
| 未验证邮箱超 10 条/天 | 401 | 40102 | 邮箱未验证（含 today_count、limit） |
| Viewer 发起写操作 | 403 | 40301 | Viewer 角色不允许写操作 |
| 对 exchange_sync 改业务字段 | 403 | 40007 | 交易所同步的交易记录仅允许更新标签/备注/策略关联（含 readonly_fields） |
| 删 exchange_sync 的 trade | 403 | 40300 | 交易所同步的交易记录不可删除 |
| trade_id 不存在 | 404 | 40400 | 交易记录不存在 |
