# 币种分析

> 币种分析：行情、K 线、技术指标与对比分析。

## 接口列表

| 方法 | 路径 | 简介 |
|---|---|---|
| `GET` | `/api/v1/coins` | [获取热门币种列表](#get-api-v1-coins) |
| `GET` | `/api/v1/coins/compare` | [多币种对比](#get-api-v1-coins-compare) |
| `GET` | `/api/v1/coins/health` | [健康检查](#get-api-v1-coins-health) |
| `GET` | `/api/v1/coins/{symbol}` | [获取币种基本信息](#get-api-v1-coins-symbol) |
| `GET` | `/api/v1/coins/{symbol}/indicators` | [获取技术指标](#get-api-v1-coins-symbol-indicators) |
| `GET` | `/api/v1/coins/{symbol}/kline` | [获取 K 线数据](#get-api-v1-coins-symbol-kline) |
| `GET` | `/api/v1/coins/{symbol}/ticker` | [获取实时行情](#get-api-v1-coins-symbol-ticker) |


## GET `/api/v1/coins`

**获取热门币种列表**

获取热门币种列表（按 24h 成交额排序）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| limit | query | integer | 否 | 数量 |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/coins/compare`

**多币种对比**

多币种对比分析。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| symbols | query | string | 是 | 交易对列表，逗号分隔，如 BTC/USDT,ETH/USDT |
| timeframe | query | string | 否 | 时间周期 |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/coins/health`

**健康检查**

币种分析模块健康检查。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## GET `/api/v1/coins/{symbol}`

**获取币种基本信息**

获取币种基本信息（含实时行情）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| symbol | path | string | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/coins/{symbol}/indicators`

**获取技术指标**

获取技术指标（RSI/MACD/MA/布林带等）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| symbol | path | string | 是 |  |
| timeframe | query | string | 否 | 时间周期 |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/coins/{symbol}/kline`

**获取 K 线数据**

获取 K 线数据。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| symbol | path | string | 是 |  |
| timeframe | query | string | 否 | 时间周期：1m/5m/1h/1d |
| limit | query | integer | 否 | K 线数量 |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/coins/{symbol}/ticker`

**获取实时行情**

获取币种实时行情。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| symbol | path | string | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |
