# 交易记录

> 交易记录：查询、标签管理、CSV 导入/导出。

## 接口列表

| 方法 | 路径 | 简介 |
|---|---|---|
| `GET` | `/api/v1/trades` | [查询交易记录列表](#get-api-v1-trades) |
| `GET` | `/api/v1/trades/export` | [导出交易记录](#get-api-v1-trades-export) |
| `GET` | `/api/v1/trades/health` | [健康检查](#get-api-v1-trades-health) |
| `POST` | `/api/v1/trades/import` | [批量导入交易记录](#post-api-v1-trades-import) |
| `GET` | `/api/v1/trades/{trade_id}` | [获取交易详情](#get-api-v1-trades-trade-id) |
| `PATCH` | `/api/v1/trades/{trade_id}/tags` | [更新交易标签/备注](#patch-api-v1-trades-trade-id-tags) |


## GET `/api/v1/trades`

**查询交易记录列表**

查询交易记录列表（分页 + 多条件筛选）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| exchange | query | any | 否 | 交易所筛选 |
| symbol | query | any | 否 | 交易对筛选 |
| side | query | any | 否 | 方向：buy/sell |
| status | query | any | 否 | 状态筛选 |
| strategy_id | query | any | 否 | 关联策略筛选 |
| start_date | query | any | 否 | 起始时间 |
| end_date | query | any | 否 | 结束时间 |
| page | query | integer | 否 | 页码 |
| page_size | query | integer | 否 | 每页条数 |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/trades/export`

**导出交易记录**

导出交易记录（CSV/JSON）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| exchange | query | any | 否 |  |
| symbol | query | any | 否 |  |
| side | query | any | 否 |  |
| status | query | any | 否 |  |
| strategy_id | query | any | 否 |  |
| start_date | query | any | 否 |  |
| end_date | query | any | 否 |  |
| fmt | query | string | 否 | 导出格式：csv / json |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/trades/health`

**健康检查**

交易记录模块健康检查。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## POST `/api/v1/trades/import`

**批量导入交易记录**

批量导入交易记录。

### 请求参数

_(无)_

### 请求体

- `Content-Type: application/json`
  - Schema: [TradeImportRequest](./10-schemas.md#TradeImportRequest)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | account_id | string (uuid) | 是 | Account Id |
    | trades | Array<[TradeImportItem](./10-schemas.md#TradeImportItem)> | 是 | Trades |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/trades/{trade_id}`

**获取交易详情**

获取单条交易记录详情。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| trade_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## PATCH `/api/v1/trades/{trade_id}/tags`

**更新交易标签/备注**

更新交易记录的标签和备注。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| trade_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [TradeTagUpdate](./10-schemas.md#TradeTagUpdate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | tags | Array<string> | 否 | Tags |
    | note | any | 否 | Note |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |
