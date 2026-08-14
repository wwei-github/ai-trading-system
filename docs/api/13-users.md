# 用户管理接口

> **模块前缀**: `/users` ｜ **RBAC**:
> - `GET/PATCH /users/me`：所有已登录用户（本人操作）
> - `GET /users` / `PATCH /users/{id}` / `POST /users/{id}/reset-password` / `GET /users/audit-logs`：仅 **Admin**（`@require_roles("admin")`）

所有端点需 `Authorization: Bearer <access_token>`。

---

## 1. 端点清单

| # | 方法 | 路径 | 功能 | 权限 |
|---|---|---|---|---|
| 1 | GET | `/users/me` | 获取本人完整资料 | 登录 |
| 2 | PATCH | `/users/me` | 修改本人资料（昵称/邮箱；改邮箱需重验证） | 登录 |
| 3 | GET | `/users` | 全平台用户列表（分页） | Admin |
| 4 | PATCH | `/users/{user_id}` | 修改任意用户资料 + 角色 + 状态 | Admin |
| 5 | POST | `/users/{user_id}/reset-password` | 重置任意用户密码（无需旧密码） | Admin |
| 6 | GET | `/users/audit-logs` | 审计日志列表（按 action / user / 时间筛选） | Admin |

> `GET /auth/me`（返回 UserBrief）与 `GET /users/me`（返回完整 UserListItem）是两个接口；前者用在全局 Header 头像显示，后者在"个人设置"页面使用。

---

## 2. 公共数据模型

### 2.1 UserListItem（用户列表 + 本人 + Admin 修改后返回）

```json
{
  "id": "uuid",
  "email": "trader@example.com",
  "nickname": "小交易员",
  "role": "trader",
  "email_verified": true,
  "totp_enabled": false,
  "is_active": true,
  "risk_agreed_at": "2026-08-01T12:00:00Z",
  "last_login_at": "2026-08-14T10:00:00Z",
  "created_at": "2026-08-01T12:00:00Z",
  "updated_at": "2026-08-14T10:00:00Z"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `role` | string | `admin` / `trader` / `viewer`（**仅 Admin 能通过 PATCH 修改**） |
| `is_active` | bool | 封禁开关；false 时所有接口返回 401（"账号已停用"） |
| `risk_agreed_at` | datetime \| null | 风险提示协议签署时间 |
| `last_login_at` | datetime \| null | 最近一次成功登录 |

---

## 3. 接口详情

### 3.1 GET `/users/me` 本人资料

**请求参数**：无。

**响应**：`UserListItem`（§2.1）。

---

### 3.2 PATCH `/users/me` 更新本人资料

**请求体 `UserUpdateRequest`**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `nickname` | string \| null | 1~100 字符 |
| `email` | EmailStr \| null | 新邮箱 |

**邮箱变更规则**：
- 若 `email` 与原值不同：
  1. 冲突检查（另一用户已使用该邮箱 → 400）。
  2. `email_verified=false`（强制需要重新验证；前端引导用户去邮箱验证流程）。
- `role` / `is_active` / `totp_enabled`：本人**不能通过此接口改**。
  - 改角色、启用/禁用账号 → 联系管理员（Admin 走 §3.4）。
  - 关 2FA → 走 `POST /auth/2fa/disable`（需旧 2FA 码）。
  - 开 2FA → 走 `/auth/2fa/setup → /auth/2fa/enable`。

**响应**：更新后的 `UserListItem`。

---

### 3.3 GET `/users` 用户列表（Admin 仅）

**查询参数**：

| 参数 | 类型 | 默认 |
|---|---|---|
| `page` | int | 1 |
| `page_size` | int | 20（1~100） |

**响应**（简化分页）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [ UserListItem, UserListItem, ... ],
    "page": 1,
    "page_size": 20,
    "total": 2
  }
}
```

> 说明：当前实现 `total` 等于 `len(items)`（≤ page_size），这是个简化 bug；生产环境应改为 `COUNT(*)` 子查询。

权限不足（非 Admin）→ 403 `无权限执行该操作`。

---

### 3.4 PATCH `/users/{user_id}` Admin 更新用户

**路径参数**：`user_id`（字符串形式的 UUID）。非法格式 → 400 `user_id 非法`。

**请求体 `UserAdminUpdateRequest`**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `nickname` | string \| null | 昵称 |
| `role` | enum \| null | `admin` / `trader` / `viewer` |
| `is_active` | bool \| null | 启用 / 禁用（禁用 → 用户再次请求接口 401） |
| `email_verified` | bool \| null | 邮箱验证标记（管理员可手动补打，如邮件服务异常） |

**典型场景**：
1. 新同事入职后分配管理员：`{"role": "admin"}`。
2. 离职用户冻结账号：`{"is_active": false}`。
3. 用户忘记验证邮件 + 邮件服务挂了：`{"email_verified": true}`。

**响应**：修改后的 `UserListItem`；找不到用户 → 404。

> 审计：此操作会被 `audit_middleware` 自动记录为 `action=update / resource_type=user`，含 before/after diff。

---

### 3.5 POST `/users/{user_id}/reset-password` Admin 重置密码

**请求体**：

```json
{"new_password": "NewPass123"}
```

| 字段 | 必填 | 校验 |
|---|---|---|
| `new_password` | ✅ | ≥8 含字母 + 数字；bcrypt 后写 `hashed_password` |

- 不需要旧密码。
- 成功后**吊销该用户所有 refresh_token**（全设备下线）。用户下次登录需用新密码。
- 响应：`{"code":0, "message":"密码已重置", "data":null}`。
- 找不到用户 → 404。

---

### 3.6 GET `/users/audit-logs` 审计日志（Admin 仅）

审计日志由 `app/middleware/audit_middleware.py` 或 `write_audit_log()` 写入 `audit_logs` 表；每条写操作均会记录（含 before/after diff、敏感字段已脱敏）。

**查询参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `action` | string | 动作过滤：`create / update / delete / import / export / login / logout / password_change / sync / system_config` |
| `resource_type` | string | 资源类型：`user / account / trade / trade_tag / strategy / book / system_config` |
| `resource_id` | uuid | 资源 ID |
| `operator_user_id` | uuid | 操作人 |
| `start_date` | datetime | 时间范围起 |
| `end_date` | datetime | 时间范围止 |
| `page` | int | 默认 1 |
| `page_size` | int | 默认 20 |

**响应字段**（每条记录）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | 主键 |
| `operator_user_id` | uuid | 操作人 |
| `operator_email` | string | 操作人邮箱（join 用） |
| `action` | string | 10 类动作 |
| `resource_type` | string | 资源类型 |
| `resource_id` | uuid \| null | 资源主键 |
| `detail` | dict \| null | before/after diff 或其他参数；字段经 `mask_sensitive()` 脱敏 |
| `ip` | string \| null | 操作人 IP（来自 Request 头 `X-Forwarded-For` 或 `request.client.host`） |
| `user_agent` | string \| null | User-Agent |
| `created_at` | datetime | 操作时间 |

---

## 4. 错误示例速查

| 场景 | HTTP | code | message |
|---|---|---|---|
| 邮箱变更时冲突 | 400 | 40000 | 邮箱已被使用 |
| user_id 非 UUID 格式 | 400 | 40000 | user_id 非法 |
| 非 Admin 调 `/users` 等接口 | 403 | 40300 | 无权限执行该操作（require_roles=admin） |
| 用户 ID 不存在 | 404 | 40400 | 用户不存在 |
