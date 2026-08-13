# 系统管理

> 系统管理：用户、配置、通知、审计日志。

## 接口列表

| 方法 | 路径 | 简介 |
|---|---|---|
| `GET` | `/api/v1/system/audit-logs` | [获取审计日志](#get-api-v1-system-audit-logs) |
| `GET` | `/api/v1/system/config` | [获取系统配置](#get-api-v1-system-config) |
| `PATCH` | `/api/v1/system/config` | [更新系统配置](#patch-api-v1-system-config) |
| `GET` | `/api/v1/system/health` | [健康检查](#get-api-v1-system-health) |
| `GET` | `/api/v1/system/info` | [系统信息](#get-api-v1-system-info) |
| `GET` | `/api/v1/system/notifications` | [获取通知设置](#get-api-v1-system-notifications) |
| `PATCH` | `/api/v1/system/notifications` | [更新通知设置](#patch-api-v1-system-notifications) |
| `GET` | `/api/v1/system/users` | [获取用户列表](#get-api-v1-system-users) |
| `POST` | `/api/v1/system/users` | [创建用户](#post-api-v1-system-users) |
| `PATCH` | `/api/v1/system/users/{user_id}` | [更新用户](#patch-api-v1-system-users-user-id) |


## GET `/api/v1/system/audit-logs`

**获取审计日志**

获取审计日志列表（分页 + 筛选）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| user_id | query | string (uuid) | 否 | 按用户筛选 |
| action | query | string | 否 | 按动作筛选 |
| resource_type | query | string | 否 | 按资源类型筛选 |
| page | query | integer | 否 | 页码，从 1 开始 |
| page_size | query | integer | 否 | 每页条数，最大 100 |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/system/config`

**获取系统配置**

获取系统配置。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## PATCH `/api/v1/system/config`

**更新系统配置**

更新系统配置（当前运行时配置通过环境变量管理，此接口预留）。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## GET `/api/v1/system/health`

**健康检查**

系统模块健康检查。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## GET `/api/v1/system/info`

**系统信息**

获取系统信息。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## GET `/api/v1/system/notifications`

**获取通知设置**

获取通知设置。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## PATCH `/api/v1/system/notifications`

**更新通知设置**

更新通知设置。

### 请求参数

_(无)_

### 请求体

- `Content-Type: application/json`
  - Schema: [NotificationSettings](./10-schemas.md#NotificationSettings)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | email_notification | boolean | 否 | Email Notification |
    | desktop_notification | boolean | 否 | Desktop Notification |
    | trade_signal_alert | boolean | 否 | Trade Signal Alert |
    | sync_failure_alert | boolean | 否 | Sync Failure Alert |
    | report_frequency | string | 否 | Report Frequency |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/system/users`

**获取用户列表**

获取用户列表（分页）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| page | query | integer | 否 | 页码，从 1 开始 |
| page_size | query | integer | 否 | 每页条数，最大 100 |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## POST `/api/v1/system/users`

**创建用户**

创建用户。

### 请求参数

_(无)_

### 请求体

- `Content-Type: application/json`
  - Schema: [UserCreate](./10-schemas.md#UserCreate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | email | string | 是 | 邮箱 |
    | nickname | string | 是 | 昵称 |
    | role | string | 否 | 角色：admin / trader / viewer |
    | is_active | boolean | 否 | 是否激活 |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## PATCH `/api/v1/system/users/{user_id}`

**更新用户**

更新用户信息。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| user_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [UserUpdate](./10-schemas.md#UserUpdate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | email | any | 否 | Email |
    | nickname | any | 否 | Nickname |
    | role | any | 否 | Role |
    | is_active | any | 否 | Is Active |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |
