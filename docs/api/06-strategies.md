# 策略管理

> 策略管理：策略 CRUD、参数配置、回测触发、模拟/实盘交易。

## 接口列表

| 方法 | 路径 | 简介 |
|---|---|---|
| `GET` | `/api/v1/strategies` | [获取策略列表](#get-api-v1-strategies) |
| `POST` | `/api/v1/strategies` | [创建策略](#post-api-v1-strategies) |
| `GET` | `/api/v1/strategies/health` | [健康检查](#get-api-v1-strategies-health) |
| `DELETE` | `/api/v1/strategies/{strategy_id}` | [删除策略](#delete-api-v1-strategies-strategy-id) |
| `GET` | `/api/v1/strategies/{strategy_id}` | [获取策略详情](#get-api-v1-strategies-strategy-id) |
| `PATCH` | `/api/v1/strategies/{strategy_id}` | [更新策略](#patch-api-v1-strategies-strategy-id) |
| `POST` | `/api/v1/strategies/{strategy_id}/backtest` | [触发策略回测](#post-api-v1-strategies-strategy-id-backtest) |
| `GET` | `/api/v1/strategies/{strategy_id}/backtests` | [获取回测历史](#get-api-v1-strategies-strategy-id-backtests) |
| `POST` | `/api/v1/strategies/{strategy_id}/live-trade` | [实盘交易](#post-api-v1-strategies-strategy-id-live-trade) |
| `POST` | `/api/v1/strategies/{strategy_id}/paper-trade` | [模拟交易](#post-api-v1-strategies-strategy-id-paper-trade) |


## GET `/api/v1/strategies`

**获取策略列表**

获取当前用户的全部策略。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## POST `/api/v1/strategies`

**创建策略**

创建策略。

### 请求参数

_(无)_

### 请求体

- `Content-Type: application/json`
  - Schema: [StrategyCreate](./10-schemas.md#StrategyCreate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | name | string | 是 | 策略名称 |
    | category | string | 是 | 策略类别 |
    | description | any | 否 | Description |
    | rules | any | 否 | Rules |
    | params | any | 否 | Params |
    | source_book_id | any | 否 | Source Book Id |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 201 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/strategies/health`

**健康检查**

策略模块健康检查。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## DELETE `/api/v1/strategies/{strategy_id}`

**删除策略**

删除策略。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| strategy_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/strategies/{strategy_id}`

**获取策略详情**

获取策略详情。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| strategy_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## PATCH `/api/v1/strategies/{strategy_id}`

**更新策略**

更新策略信息。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| strategy_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [StrategyUpdate](./10-schemas.md#StrategyUpdate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | name | any | 否 | Name |
    | description | any | 否 | Description |
    | rules | any | 否 | Rules |
    | params | any | 否 | Params |
    | status | any | 否 | Status |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## POST `/api/v1/strategies/{strategy_id}/backtest`

**触发策略回测**

触发策略回测（异步任务）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| strategy_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [BacktestCreate](./10-schemas.md#BacktestCreate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | strategy_id | string (uuid) | 是 | Strategy Id |
    | symbol | string | 是 | Symbol |
    | timeframe | string | 否 | Timeframe |
    | start_date | string (date) | 是 | Start Date |
    | end_date | string (date) | 是 | End Date |
    | initial_capital | any | 否 | Initial Capital |
    | params | any | 否 | Params |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 201 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/strategies/{strategy_id}/backtests`

**获取回测历史**

获取策略的回测历史。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| strategy_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## POST `/api/v1/strategies/{strategy_id}/live-trade`

**实盘交易**

实盘交易（需二次确认）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| strategy_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [LiveTradeRequest](./10-schemas.md#LiveTradeRequest)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | symbol | string | 是 | Symbol |
    | side | string | 是 | Side |
    | order_type | string | 否 | Order Type |
    | amount | number | 是 | Amount |
    | price | any | 否 | Price |
    | account_id | string (uuid) | 是 | Account Id |
    | confirm | boolean | 否 | 必须为 true 才会执行实盘下单 |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## POST `/api/v1/strategies/{strategy_id}/paper-trade`

**模拟交易**

模拟交易（不实际下单）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| strategy_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [PaperTradeRequest](./10-schemas.md#PaperTradeRequest)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | symbol | string | 是 | Symbol |
    | side | string | 是 | Side |
    | amount | number | 是 | Amount |
    | price | any | 否 | Price |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |
