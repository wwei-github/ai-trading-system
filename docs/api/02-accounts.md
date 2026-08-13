# 交易所账号

> 交易所账号管理：绑定交易所 API 凭证，用于交易记录同步与交易下单。

## 接口列表

| 方法 | 路径 | 简介 |
|---|---|---|
| `GET` | `/api/v1/accounts` | [获取账号列表](#get-api-v1-accounts) |
| `POST` | `/api/v1/accounts` | [创建交易所账号](#post-api-v1-accounts) |
| `GET` | `/api/v1/accounts/health` | [健康检查](#get-api-v1-accounts-health) |
| `DELETE` | `/api/v1/accounts/{account_id}` | [删除账号](#delete-api-v1-accounts-account-id) |
| `GET` | `/api/v1/accounts/{account_id}` | [获取账号详情](#get-api-v1-accounts-account-id) |
| `PATCH` | `/api/v1/accounts/{account_id}` | [更新账号信息](#patch-api-v1-accounts-account-id) |
| `GET` | `/api/v1/accounts/{account_id}/balance` | [查询账号余额](#get-api-v1-accounts-account-id-balance) |
| `POST` | `/api/v1/accounts/{account_id}/sync` | [触发订单/交易同步](#post-api-v1-accounts-account-id-sync) |
| `POST` | `/api/v1/accounts/{account_id}/test` | [测试交易所连接](#post-api-v1-accounts-account-id-test) |


## GET `/api/v1/accounts`

**获取账号列表**

获取当前用户的全部交易所账号。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## POST `/api/v1/accounts`

**创建交易所账号**

创建交易所账号（API Key 加密存储）。

### 请求参数

_(无)_

### 请求体

- `Content-Type: application/json`
  - Schema: [ExchangeAccountCreate](./10-schemas.md#ExchangeAccountCreate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | exchange | string | 是 | 交易所名称 |
    | label | string | 是 | 账号标签 |
    | api_key | string | 是 | API Key（明文，传输后加密存储） |
    | api_secret | string | 是 | API Secret（明文） |
    | passphrase | any | 否 | 口令（OKX 等） |
    | permissions | any | 否 | 权限列表 |
    | is_testnet | boolean | 否 | 是否为测试网 |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 201 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/accounts/health`

**健康检查**

账号模块健康检查。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## DELETE `/api/v1/accounts/{account_id}`

**删除账号**

删除交易所账号。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| account_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/accounts/{account_id}`

**获取账号详情**

获取交易所账号详情。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| account_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## PATCH `/api/v1/accounts/{account_id}`

**更新账号信息**

更新交易所账号信息。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| account_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [ExchangeAccountUpdate](./10-schemas.md#ExchangeAccountUpdate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | label | any | 否 | Label |
    | permissions | any | 否 | Permissions |
    | is_testnet | any | 否 | Is Testnet |
    | status | any | 否 | Status |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/accounts/{account_id}/balance`

**查询账号余额**

查询交易所账号余额。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| account_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## POST `/api/v1/accounts/{account_id}/sync`

**触发订单/交易同步**

触发指定账号的交易记录同步（异步任务）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| account_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## POST `/api/v1/accounts/{account_id}/test`

**测试交易所连接**

测试交易所连接是否正常。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| account_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |
