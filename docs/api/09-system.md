# 09-系统管理接口文档（Stage 8）

> 模块：系统设置 + 用户管理 + 审计日志
> 对齐 PRD：§5.9.1 ~ §5.9.3
> Base URL：`/api/v1/system`

---

## 目录

1. [系统信息](#1-系统信息)
2. [用户管理](#2-用户管理)
3. [运行时配置](#3-运行时配置)
4. [系统配置 CRUD（持久化）](#4-系统配置-crud持久化)
5. [通知设置](#5-通知设置)
6. [审计日志](#6-审计日志)
7. [权限说明](#7-权限说明)
8. [数据模型](#8-数据模型)

---

## 1. 系统信息

### 1.1 健康检查

```
GET /system/health
```

无需认证。

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "ok",
    "module": "system",
    "app_env": "local",
    "debug": true
  }
}
```

### 1.2 系统信息

```
GET /system/info
```

返回应用基础信息。

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "app_name": "AI 交易系统",
    "app_env": "local",
    "api_prefix": "/api/v1",
    "version": "1.0.0"
  }
}
```

---

## 2. 用户管理

### 2.1 获取用户列表

```
GET /system/users?page=1&page_size=20
```

分页返回用户列表。

**查询参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页条数 |

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total": 3,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "id": "uuid",
        "email": "admin@example.com",
        "nickname": "管理员",
        "role": "admin",
        "is_active": true,
        "created_at": "2026-08-14T10:00:00Z",
        "updated_at": "2026-08-14T10:00:00Z"
      }
    ]
  }
}
```

### 2.2 创建用户

```
POST /system/users
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 邮箱 |
| nickname | string | 是 | 昵称 |
| role | string | 否 | 角色：admin / trader / viewer（默认 trader） |
| is_active | bool | 否 | 是否激活（默认 true） |

### 2.3 更新用户

```
PATCH /system/users/{user_id}
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 否 | 邮箱 |
| nickname | string | 否 | 昵称 |
| role | string | 否 | 角色 |
| is_active | bool | 否 | 是否激活 |

**错误响应：** 用户不存在返回 `code: 404`。

---

## 3. 运行时配置

### 3.1 获取运行时配置

```
GET /system/config
```

返回由环境变量控制的运行时配置。**仅 Admin 可访问。**

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "app_name": "AI 交易系统",
    "app_env": "local",
    "api_prefix": "/api/v1",
    "debug": true,
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini"
  }
}
```

### 3.2 更新运行时配置（预留）

```
PATCH /system/config
```

> 当前运行时配置通过环境变量管理，此接口预留扩展。调用后返回当前配置。

---

## 4. 系统配置 CRUD（持久化）

> 以下接口操作 `system_configs` 表，以 `category + key` 唯一标识配置项，`value` 为 JSONB 结构。**全部仅 Admin 可访问。**

### 4.1 获取配置项列表

```
GET /system/configs?category=ai
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| category | string | 否 | 按分类筛选：ai / exchanges / risk / notifications / storage |

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "uuid",
      "category": "ai",
      "key": "default_model",
      "value": {"provider": "openai", "model": "gpt-4o-mini"},
      "description": "AI 默认模型配置",
      "created_at": "2026-08-14T10:00:00Z",
      "updated_at": "2026-08-14T10:00:00Z"
    }
  ]
}
```

### 4.2 创建/更新配置项（Upsert）

```
POST /system/configs
```

基于 `category + key` 唯一约束：存在则更新，不存在则创建。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| category | string | 是 | 配置分类（最长 50 字符） |
| key | string | 是 | 配置键（最长 100 字符，分类内唯一） |
| value | object | 是 | 配置值（JSONB 结构） |
| description | string | 否 | 配置描述 |

**请求示例：**

```json
{
  "category": "risk",
  "key": "max_position_pct",
  "value": {"value": 0.3, "unit": "percent"},
  "description": "单币种最大持仓比例"
}
```

**返回结果（HTTP 201）：** 同 4.1 单条配置项对象。

### 4.3 获取单个配置项

```
GET /system/configs/{category}/{key}
```

**错误响应：** 配置项不存在返回 404。

### 4.4 更新配置项

```
PATCH /system/configs/{category}/{key}
```

仅更新 `value` 和 `description`，`category` 和 `key` 不可变。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| value | object | 是 | 新的配置值 |
| description | string | 否 | 新的描述 |

**错误响应：** 配置项不存在返回 404。

### 4.5 删除配置项

```
DELETE /system/configs/{category}/{key}
```

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {"deleted": true}
}
```

**错误响应：** 配置项不存在返回 404。

### 配置分类约定

| 分类 | 用途 | 示例 key |
|------|------|----------|
| `ai` | AI 模型相关 | default_model、temperature、max_tokens |
| `exchanges` | 交易所相关 | default_exchange、sync_interval |
| `risk` | 风控参数 | max_position_pct、max_drawdown |
| `notifications` | 通知渠道 | email_smtp、webhook_url |
| `storage` | 存储相关 | upload_max_size、backup_retention |

---

## 5. 通知设置

### 5.1 获取通知设置

```
GET /system/notifications
```

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "email_notification": true,
    "desktop_notification": true,
    "trade_signal_alert": true,
    "sync_failure_alert": true,
    "report_frequency": "daily"
  }
}
```

### 5.2 更新通知设置

```
PATCH /system/notifications
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email_notification | bool | 否 | 邮件通知 |
| desktop_notification | bool | 否 | 桌面通知 |
| trade_signal_alert | bool | 否 | 交易信号提醒 |
| sync_failure_alert | bool | 否 | 同步失败提醒 |
| report_frequency | string | 否 | 报告频率：daily / weekly / monthly |

> 当前为内存默认值，后续可持久化到 system_configs 表。

---

## 6. 审计日志

### 6.1 获取审计日志列表

```
GET /system/audit-logs?page=1&page_size=20
```

分页返回审计日志，**仅 Admin 可访问**。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码（默认 1） |
| page_size | int | 否 | 每页条数（默认 20） |
| user_id | UUID | 否 | 按用户筛选 |
| action | string | 否 | 按动作筛选：create / update / delete / sync 等 |
| resource_type | string | 否 | 按资源类型筛选：account / trade / strategy 等 |

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total": 128,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "id": "uuid",
        "user_id": "uuid",
        "action": "create",
        "resource_type": "account",
        "resource_id": "uuid",
        "detail": {"exchange": "binance", "name": "主账户"},
        "ip": "192.168.1.1",
        "created_at": "2026-08-14T10:00:00Z"
      }
    ]
  }
}
```

### 6.2 导出审计日志为 CSV

```
GET /system/audit-logs/export
```

导出审计日志为 CSV 文件（带 UTF-8 BOM，兼容 Excel），**仅 Admin 可访问**。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | UUID | 否 | 按用户筛选 |
| action | string | 否 | 按动作筛选 |
| resource_type | string | 否 | 按资源类型筛选 |
| start_time | datetime | 否 | 起始时间（ISO 8601） |
| end_time | datetime | 否 | 结束时间（ISO 8601） |
| limit | int | 否 | 导出条数上限（默认 10000，最大 50000） |

**响应：**

- Content-Type：`text/csv; charset=utf-8`
- Content-Disposition：`attachment; filename="audit_logs_20260814_100000.csv"`

**CSV 列：**

| 列 | 说明 |
|----|------|
| ID | 日志 ID |
| 时间 | 操作时间（`YYYY-MM-DD HH:MM:SS`） |
| 用户ID | 操作用户 ID |
| 用户邮箱 | 操作用户邮箱（关联查询） |
| 动作 | 操作动作 |
| 资源类型 | 资源类型 |
| 资源ID | 资源 ID |
| IP地址 | 操作 IP |
| 操作详情 | 详情（JSON 字符串） |

**CSV 示例：**

```csv
ID,时间,用户ID,用户邮箱,动作,资源类型,资源ID,IP地址,操作详情
"uuid","2026-08-14 10:00:00","uuid","admin@example.com","create","account","uuid","192.168.1.1","{'exchange': 'binance', 'name': '主账户'}"
```

---

## 7. 权限说明

### 角色权限矩阵

| 接口分组 | Admin | Trader | Viewer |
|----------|-------|--------|--------|
| 系统信息 / 健康检查 | ✓ | ✓ | ✓ |
| 通知设置（读写自己的） | ✓ | ✓ | ✓ |
| 用户列表 / 创建 / 更新 | ✓ | ✗ | ✗ |
| 运行时配置（GET /config） | ✓ | ✗ | ✗ |
| 系统配置 CRUD（/configs） | ✓ | ✗ | ✗ |
| 审计日志（列表 + CSV 导出） | ✓ | ✗ | ✗ |

### 权限校验机制

- 使用 `require_roles("admin")` 依赖进行角色校验
- 非 Admin 访问受保护接口返回 403 Forbidden
- 用户只能操作自己的通知设置，不能访问他人数据

---

## 8. 数据模型

### SystemConfig（系统配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| category | string(50) | 配置分类（索引） |
| key | string(100) | 配置键 |
| value | JSONB | 配置值（支持复杂结构） |
| description | text | 配置描述 |

**唯一约束：** `(category, key)` 联合唯一。

### AuditLog（审计日志）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 操作用户（可空，如系统操作） |
| action | string(50) | 动作：create / update / delete / sync 等 |
| resource_type | string(50) | 资源类型：account / trade / strategy 等 |
| resource_id | string(100) | 资源 ID |
| detail | JSONB | 操作详情 |
| ip | string(50) | 操作 IP |
| user_agent | string(255) | User-Agent |

### User（用户）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| email | string | 邮箱（唯一） |
| nickname | string | 昵称 |
| role | string | 角色：admin / trader / viewer |
| is_active | bool | 是否激活 |
| hashed_password | string | 密码哈希 |
