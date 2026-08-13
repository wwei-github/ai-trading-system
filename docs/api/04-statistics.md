# 统计分析

> 统计分析：交易表现、盈亏分布、资产趋势、排行榜。

## 接口列表

| 方法 | 路径 | 简介 |
|---|---|---|
| `GET` | `/api/v1/statistics/asset-trend` | [资产趋势](#get-api-v1-statistics-asset-trend) |
| `GET` | `/api/v1/statistics/coins` | [币种维度统计](#get-api-v1-statistics-coins) |
| `GET` | `/api/v1/statistics/exchange-distribution` | [交易所分布](#get-api-v1-statistics-exchange-distribution) |
| `GET` | `/api/v1/statistics/export` | [报表导出](#get-api-v1-statistics-export) |
| `GET` | `/api/v1/statistics/health` | [健康检查](#get-api-v1-statistics-health) |
| `GET` | `/api/v1/statistics/monthly-report` | [月度报表](#get-api-v1-statistics-monthly-report) |
| `GET` | `/api/v1/statistics/pnl` | [盈亏按周期统计](#get-api-v1-statistics-pnl) |
| `GET` | `/api/v1/statistics/side-distribution` | [买卖方向分布](#get-api-v1-statistics-side-distribution) |
| `GET` | `/api/v1/statistics/strategy-comparison` | [策略收益对比](#get-api-v1-statistics-strategy-comparison) |
| `GET` | `/api/v1/statistics/summary` | [交易汇总指标](#get-api-v1-statistics-summary) |
| `GET` | `/api/v1/statistics/time-distribution` | [交易时间分布](#get-api-v1-statistics-time-distribution) |


## GET `/api/v1/statistics/asset-trend`

**资产趋势**

资产趋势（面积图数据）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| account_id | query | any | 否 | 按账号筛选 |
| days | query | integer | 否 | 天数 |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/statistics/coins`

**币种维度统计**

按币种维度统计（柱状图数据）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| start_date | query | any | 否 |  |
| end_date | query | any | 否 |  |
| symbol | query | any | 否 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/statistics/exchange-distribution`

**交易所分布**

按交易所分布统计（饼图数据）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| start_date | query | any | 否 |  |
| end_date | query | any | 否 |  |
| symbol | query | any | 否 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/statistics/export`

**报表导出**

导出统计报表为 CSV。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| start_date | query | any | 否 |  |
| end_date | query | any | 否 |  |
| symbol | query | any | 否 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/statistics/health`

**健康检查**

统计分析模块健康检查。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## GET `/api/v1/statistics/monthly-report`

**月度报表**

获取月度报表。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| year | query | any | 否 | 年份，默认当前年 |
| month | query | any | 否 | 月份，默认当前月 |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/statistics/pnl`

**盈亏按周期统计**

盈亏按周期统计（折线图数据）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| period | query | string | 否 | 周期：daily/weekly/monthly |
| start_date | query | any | 否 |  |
| end_date | query | any | 否 |  |
| symbol | query | any | 否 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/statistics/side-distribution`

**买卖方向分布**

按买卖方向分布统计。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| start_date | query | any | 否 |  |
| end_date | query | any | 否 |  |
| symbol | query | any | 否 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/statistics/strategy-comparison`

**策略收益对比**

策略收益对比。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## GET `/api/v1/statistics/summary`

**交易汇总指标**

获取交易汇总指标（总笔数、成交额、手续费、胜率等）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| start_date | query | any | 否 |  |
| end_date | query | any | 否 |  |
| symbol | query | any | 否 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/statistics/time-distribution`

**交易时间分布**

按交易时间（小时）分布统计。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| start_date | query | any | 否 |  |
| end_date | query | any | 否 |  |
| symbol | query | any | 否 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |
