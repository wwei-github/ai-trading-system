# 认证鉴权接口

> **模块前缀**: `/auth` ｜ **前缀**: `/api/v1`
> **认证方式**: JWT Bearer Token（`access_token` / `refresh_token`）
> **密码复杂度**: ≥8 位，至少含字母 + 数字（bcrypt 哈希；bcrypt 4.0.1，≤72 bytes 限制）
> **登录锁定**: 密码错误 ≥5 次 → 锁定 30 分钟（`failed_login_attempts` / `locked_until`）
> **限流**: 登录接口 1 分钟 10 次（IP 维度）

---

## 1. 端点清单

| # | 方法 | 路径 | 功能 | 是否需要 Token |
|---|---|---|---|---|
| 1 | POST | `/auth/register` | 注册 | 否 |
| 2 | POST | `/auth/verify-email` | 邮箱验证 | 否 |
| 3 | POST | `/auth/resend-verification` | 重发邮箱验证码 | 否 |
| 4 | POST | `/auth/login` | 登录（Access + Refresh） | 否 |
| 5 | POST | `/auth/logout` | 登出（吊销 refresh_token） | 否（需传 refresh_token） |
| 6 | POST | `/auth/refresh` | 刷新 Access Token | 否（需传 refresh_token） |
| 7 | POST | `/auth/forgot-password/send` | 发送密码找回验证码 | 否 |
| 8 | POST | `/auth/forgot-password/reset` | 验证码 + 新密码 | 否 |
| 9 | POST | `/auth/change-password` | 已登录修改密码 | ✅（Access） |
| 10 | POST | `/auth/2fa/setup` | 2FA 设置（返回 QR 码 URI） | ✅ |
| 11 | POST | `/auth/2fa/enable` | 确认开启 2FA（校验 App 输入的 6 位码） | ✅ |
| 12 | POST | `/auth/2fa/disable` | 关闭 2FA（同样要求 2FA 码） | ✅ |
| 13 | GET | `/auth/devices` | 当前用户登录设备列表 | ✅ |
| 14 | DELETE | `/auth/devices/{device_id}` | 强制下线指定设备（吊销该 refresh_token） | ✅ |
| 15 | GET | `/auth/me` | 当前用户简要信息 | ✅ |

---

## 2. 公共数据模型

### 2.1 TokenPair（登录 / refresh 统一返回）

```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXBlIjoicmVm...",
    "token_type": "bearer",
    "expires_in": 1800,
    "user": {
      "id": "uuid",
      "email": "trader@example.com",
      "nickname": "小交易员",
      "role": "trader",
      "email_verified": true,
      "totp_enabled": false,
      "risk_agreed_at": "2026-08-01T12:00:00Z"
    }
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `access_token` | JWT | 默认有效期 30 分钟；`jwt[type]=access` |
| `refresh_token` | JWT | 7 天（`remember_me=true` → 30 天）；`jwt[type]=refresh`，`jwt[device_id]=uuid` |
| `expires_in` | int | access_token 剩余秒数（前端用于提前刷新） |
| `user.role` | string | `admin` / `trader` / `viewer`（注册默认 `trader`） |
| `user.totp_enabled` | bool | 若 true，登录必须传 `totp_code`（6 位数字） |

### 2.2 UserBrief（/me 返回）

同 TokenPair.data.user；只带本人概要信息，不含密码相关字段。

---

## 3. 接口详情

### 3.1 POST `/auth/register` 注册

**请求体 `RegisterRequest`**：

| 字段 | 必填 | 类型 | 校验 |
|---|---|---|---|
| `email` | ✅ | EmailStr | 全局唯一；若重复 → 40001 |
| `password` | ✅ | string | ≥8 且含字母 + 数字；bcrypt 上限 72 字节（长密码会被截断） |
| `nickname` | ✅ | string | 1~100 字符 |
| `risk_agreed` | ✅ | bool | 必须为 true；否则 400 |

**响应**：

```json
{
  "code": 0,
  "message": "注册成功，请查收邮箱验证码",
  "data": {
    "user_id": "uuid",
    "email": "trader@example.com"
  }
}
```

- **默认角色**：注册用户初始 `role=trader`。`admin` 只能在初始化脚本或由其他 Admin 变更。
- **发件**：开发模式（`EMAIL_ENABLE_TEST_MODE=true`，默认）不真实发信，验证码写入日志（`backend.log` 里搜索 `【邮件验证码】`）。
- **邮件时效**：验证码 token 24 小时内有效。

---

### 3.2 POST `/auth/verify-email` 邮箱验证

**请求体**：

```json
{"code": "ev_xxxxxx"}
```

成功后用户 `email_verified=true`；失败返回 40004（过期）或 400（校验失败）。

---

### 3.3 POST `/auth/resend-verification` 重发邮箱验证码

**请求体**：

```json
{"email": "trader@example.com"}
```

**响应**：无论邮箱是否存在，消息统一为 `"若邮箱存在，验证码已发送"`（防止邮箱枚举）。

---

### 3.4 POST `/auth/login` 登录

**请求体 `LoginRequest`**：

| 字段 | 必填 | 类型 |
|---|---|---|
| `email` | ✅ | EmailStr |
| `password` | ✅ | string |
| `remember_me` | — | bool（默认 false；true → refresh 30 天） |
| `totp_code` | — | 6 位数字；**仅当 `user.totp_enabled=true` 时必填** |

**成功响应**：`TokenPair`（见 §2.1）。

**失败响应**：

| 情况 | HTTP | code | detail |
|---|---|---|---|
| 邮箱/密码错 | 400 | 40002 | `attempts: N`（连续失败计数） |
| 账号被锁定 | 400 | 40003 | `lock_minutes: 30`，`unlock_at` |
| 开启 2FA 但未传 totp_code / 码错误 | 401 | 40101 | `totp_required: true` |

> 限流：IP 1 分钟内 >10 次 → 429。登录失败计数仅在 `password` 校验时递增；连续成功后归零。

---

### 3.5 POST `/auth/logout` 登出

**请求体**：

```json
{"refresh_token": "eyJ..."}
```

服务端将该 `refresh_token` 对应 `login_devices.is_revoked=true`，
Access Token 仍可用至过期（前端建议自行清除本地存储）。

---

### 3.6 POST `/auth/refresh` 刷新 Access Token

**请求体**：

```json
{"refresh_token": "eyJ..."}
```

**校验**：
- JWT 签名 / type=refresh / 过期。
- 对应 login_device 存在且 `is_revoked=false`。
- 用户 `is_active=true`。

**成功响应**：返回**全新的一对 Token**（Refresh Token 轮转）。旧 refresh_token 被 revoke，前端应立即替换成新 pair。

**失败**：40100（token 无效 / 已吊销）。

---

### 3.7 POST `/auth/forgot-password/send` 发送找回码

**请求体**：

```json
{"email": "trader@example.com"}
```

**响应**：统一 `"若邮箱存在，验证码已发送"`（避免枚举）。

开发模式同 §3.1：验证码写日志。

---

### 3.8 POST `/auth/forgot-password/reset` 密码重置

**请求体**：

| 字段 | 必填 |
|---|---|
| `email` | ✅ |
| `code` | ✅（找回验证码；与 verify-email 独立） |
| `new_password` | ✅（≥8 含字母数字） |

成功后**吊销该用户所有 refresh_token**（全设备下线）。

---

### 3.9 POST `/auth/change-password` 修改密码（登录态）

**请求体**：

```json
{
  "old_password": "Aaaa1234",
  "new_password": "Bbbb5678"
}
```

**规则**：
- `old_password` 正确；否则 400。
- 若用户已启用 2FA，需额外在 Header 中传 `X-2FA-Token: 6位码`（高危动作二次校验；当前路由未强制，后续升级会在 `deps.py` 中补）。
- 成功后**所有设备下线**（同 §3.8）。

---

### 3.10 POST `/auth/2fa/setup` 获取 2FA 秘钥 + QR

**请求头**：`Authorization: Bearer <access_token>`。

**响应**：

```json
{
  "code": 0,
  "message": "请用 Google Authenticator 扫码",
  "data": {
    "secret": "JBSWY3DPEHPK3PXP",
    "otpauth_uri": "otpauth://totp/AI Trading:admin@trading-system.dev?secret=...&issuer=AI+Trading"
  }
}
```

前端用 `QRCode` 组件将 `otpauth_uri` 渲染为二维码，用户用 TOTP App（Google Authenticator / 1Password / Authy）扫码。

> 注意：此接口只生成临时 secret，**并未真正开启 2FA**。必须再调用 `/2fa/enable` 并提交 App 显示的 6 位码校验成功后，用户 `totp_enabled=true`。

---

### 3.11 POST `/auth/2fa/enable` 确认开启 2FA

**请求体**：

```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "code": "123456"
}
```

- `code` 必须匹配 `secret` 当前窗口（±1 窗口容忍）。
- 成功后 `users.totp_secret=secret`（已加密）且 `totp_enabled=true`。
- 后续登录必须带 `totp_code`。

---

### 3.12 POST `/auth/2fa/disable` 关闭 2FA

**请求体**：

```json
{"code": "123456"}
```

同样要求 2FA 码（防止攻击者拿到 access_token 就关 2FA）。成功后 `totp_enabled=false` 且清除 `totp_secret`。

---

### 3.13 GET `/auth/devices` 登录设备列表

**响应**：`LoginDeviceBrief[]`（按 `last_active_at` 倒序）。

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "device-uuid",
      "device_name": "Chrome · macOS",
      "ip": "127.0.0.1",
      "last_active_at": "2026-08-14T10:00:00Z",
      "is_revoked": false
    }
  ]
}
```

> `device_name` / `ip` 从登录请求的 `User-Agent` 与客户端 IP 解析。

---

### 3.14 DELETE `/auth/devices/{device_id}` 强制下线

**路径参数**：`device_id`（uuid 字符串）。只允许操作**本人**设备（service 层按 user_id 过滤）。

- 将对应 `login_devices.is_revoked=true` → 该设备下一次 `/refresh` 失败。

---

### 3.15 GET `/auth/me` 当前用户信息

**响应**：`UserBrief`（同 §2.1 TokenPair.data.user）。

---

## 4. 错误示例速查

| 场景 | HTTP | code | message |
|---|---|---|---|
| 邮箱已存在 | 400 | 40001 | 邮箱已存在 |
| 密码强度不足 | 400 | 40000 | 密码必须包含字母 / 数字 / 长度至少 8 位 |
| 邮箱或密码错误 | 400 | 40002 | 邮箱或密码错误（含 attempts） |
| 连续失败 ≥5 次 | 400 | 40003 | 账号已被锁定（含 lock_minutes, unlock_at） |
| 邮箱验证链接过期 | 400 | 40004 | 邮箱验证链接已过期 |
| 密码找回码错误/过期 | 400 | 40000 | 验证码无效或已过期 |
| 缺少 TOTP / TOTP 错误 | 401 | 40101 | 2FA 校验失败 |
| JWT 无效 / 过期 / 已吊销 | 401 | 40100 | 未认证或 Token 无效 |
| 登录限流 | 429 | 42900 | 请求过于频繁，请稍后再试（category=login） |
