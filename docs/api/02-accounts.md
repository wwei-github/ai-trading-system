# 交易所账号接口

> **模块前缀**: `/accounts` ｜ **RBAC**: Viewer 只读 / Trader & Admin 写操作（`reject_viewer_write`）
> **敏感字段**: `api_key` / `api_secret` / `passphrase` 使用 AES-256 加密存储；响应 `api_key_masked` 为脱敏显示。

所有端点需 `Authorization: Bearer <access_token>`。

---

## 1. 端点清单

| # | 方法 | 路径 | 功能 | 权限 |
|---|---|---|---|---|
| 1 | GET | `/accounts/health` | 账号模块健康检查 | 登录 |
| 2 | GET | `/accounts/exchanges/supported` | 受支持交易所列表（含是否需 passphrase） | 登录 |
| 3 | GET | `/accounts` | 获取当前用户全部账号 | 登录 |
| 4 | POST | `/accounts` | 创建账号（AES 加密 + 连接校验） | Trader / Admin |
| 5 | GET | `/accounts/{account_id}` | 获取账号详情（api_key 脱敏） | 登录 |
| 6 | PATCH | `/accounts/{account_id}` | 更新账号（api_secret 更新需完整传入） | Trader / Admin |
| 7 | PATCH | `/accounts/{account_id}/toggle` | 启用 / 停用账号（同步任务只读取 enabled） | Trader / Admin |
| 8 | DELETE | `/accounts/{account_id}` | 删除账号（近 30 天有交易返回 400） | Trader / Admin |
| 9 | POST | `/accounts/{account_id}/test` | 测试交易所连接（success / latency_ms / permissions） | 登录 |
| 10 | GET | `/accounts/{account_id}/balance` | 查询账号余额（实时从交易所拉取） | 登录 |
| 11 | GET | `/accounts/{account_id}/snapshots` | 资产快照历史（资产曲线图用） | 登录 |
| 12 | POST | `/accounts/{account_id}/sync` | 触发订单/交易同步（Celery 异步） | Trader / Admin |

---

## 2. 公共数据模型

### 2.1 ExchangeAccountResponse（返回）

所有账号查询接口返回统一对象：

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "exchange": "binance",
  "label": "主账号",
  "api_key_masked": "xx...xxxx",
  "permissions": ["spot_read", "spot_trade"],
  "is_testnet": false,
  "status": "active",
  "is_enabled": true,
  "last_sync_at": "2026-08-14T08:00:00+00:00",
  "created_at": "2026-08-01T12:00:00+00:00",
  "updated_at": "2026-08-14T08:00:00+00:00"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | 账号 ID |
| `user_id` | uuid | 所属用户 |
| `exchange` | string | 交易所名（见 §2.3） |
| `label` | string | 用户自定义别名 |
| `api_key_masked` | string \| null | 脱敏的 API Key（首尾 2~4 位 + `...`）；创建时为 null |
| `permissions` | string[] \| null | 连接测试时读取的权限；未测试时为 null |
| `is_testnet` | bool | 是否测试网 |
| `status` | string | `active` / `inactive` / `abnormal`（同步失败 → abnormal + 邮件通知） |
| `is_enabled` | bool | 是否启用（同步任务只读取 enabled=true 的账号） |
| `last_sync_at` | datetime \| null | 上次成功同步时间 |

### 2.2 字段枚举

| 字段 | 允许值 |
|---|---|
| `exchange` | `binance` / `okx` / `bybit` / `huobi` / `gate` / `coinbase` |
| `status` | `active` / `inactive` / `abnormal` |

> **OKX / Coinbase 必填 passphrase**：创建时若 `exchange ∈ {okx, coinbase}` 但未传 `passphrase`，返回 400。
> **资金安全**：提币 / 资金划转接口 V1 固定禁用（`WithdrawDisabledError`，403）。

### 2.3 受支持交易所（返回 `SupportedExchange[]`）

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "exchanges": [
      {"name": "binance", "requires_passphrase": false, "supports_testnet": true},
      {"name": "okx",     "requires_passphrase": true,  "supports_testnet": true},
      {"name": "bybit",   "requires_passphrase": false, "supports_testnet": true},
      {"name": "huobi",   "requires_passphrase": false, "supports_testnet": true},
      {"name": "gate",    "requires_passphrase": false, "supports_testnet": true},
      {"name": "coinbase","requires_passphrase": true,  "supports_testnet": true}
    ],
    "total": 6
  }
}
```

前端创建账号表单依据 `requires_passphrase` 动态显示 passphrase 字段。

---

## 3. 接口详情

### 3.1 GET `/accounts/exchanges/supported` 支持交易所

**请求参数**：无。

**响应**：见 §2.3。

**示例**：

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:18000/api/v1/accounts/exchanges/supported
```

---

### 3.2 GET `/accounts` 账号列表

**请求参数**：无（仅返回当前 user_id）。

**响应**：`ExchangeAccountResponse[]` 数组。

**示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "exchange": "binance",
      "label": "主账号",
      "api_key_masked": "Ab...xyz",
      "is_testnet": false,
      "status": "active",
      "is_enabled": true,
      "last_sync_at": "2026-08-14T08:00:00Z"
    }
  ]
}
```

---

### 3.3 POST `/accounts` 创建账号

**请求体 `ExchangeAccountCreate`**：

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `exchange` | ✅ | string | 交易所名；不在受支持列表 → 400 |
| `label` | ✅ | string(≤50) | 别名 |
| `api_key` | ✅ | string | API Key（AES 加密存储） |
| `api_secret` | ✅ | string | API Secret（AES 加密存储） |
| `passphrase` | — | string | OKX/Coinbase 必填，其他选填 |
| `is_testnet` | — | bool | 默认 false；Binance/OKX 会切换到对应沙箱域名 |
| `permissions` | — | string[] | 预留；默认 null，连接测试后回写 |

**校验**：
- 每用户最多创建 5 个交易所账号；超出 → 400。
- exchange 不在 `SUPPORTED_EXCHANGES` → 400。
- `exchange ∈ {okx, coinbase}` 且未传 `passphrase` → 400。
- AES-256 加密后写入数据库（密钥来自 `settings.ENCRYPTION_KEY`）。

**响应**：`ExchangeAccountResponse`（`api_key_masked` = null，待调用 `/test` 后脱敏回写）。

---

### 3.4 GET `/accounts/{account_id}` 详情

**路径参数**：`account_id`（uuid）。

**响应**：`ExchangeAccountResponse`；找不到 → 404。

---

### 3.5 PATCH `/accounts/{account_id}` 更新账号

**请求体 `ExchangeAccountUpdate`**（字段均可选）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `label` | string | 别名 |
| `api_key` | string | 若更新密钥，建议同时传 api_secret；否则仅改 label |
| `api_secret` | string | 同上 |
| `passphrase` | string | OKX/Coinbase |
| `is_testnet` | bool | 切换环境 |
| `permissions` | string[] | 回写权限 |
| `status` | string | `active` / `inactive`（abnormal 仅同步任务写入） |

**响应**：`ExchangeAccountResponse`；找不到 → 404。

---

### 3.6 PATCH `/accounts/{account_id}/toggle` 启停

**请求体**：

```json
{"is_enabled": false}
```

| 字段 | 必填 | 类型 |
|---|---|---|
| `is_enabled` | ✅ | bool |

- `is_enabled=false`：Celery `sync_all_accounts` 会跳过；已在途任务不受影响。
- 同步失败的账号（status=abnormal）切换 enable 后不会自动重试，请调用 `/sync`。

**响应**：`ExchangeAccountResponse`。

---

### 3.7 DELETE `/accounts/{account_id}` 删除

**依赖检查**（`account_service.delete_account`）：
- 若存在 **近 30 天** 的关联交易 → 400 `该账号有近 30 天的关联交易记录，无法删除`；`detail.recent_trades` 为冲突数。
- 建议：先切换 `is_enabled=false`，或改"删除交易记录 → 再删账号"（交易记录需为非 exchange_sync 来源）。

**响应**：

```json
{"code": 0, "message": "ok", "data": {"deleted": true}}
```

找不到 → 404。

---

### 3.8 POST `/accounts/{account_id}/test` 连接测试

**请求体**：无（使用账号已存储的加密凭据解密后调用 `adapter.connect()`）。

**响应 `ConnectionTestResponse`**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "success": true,
    "exchange": "binance",
    "latency_ms": 142,
    "permissions": ["spot_read", "spot_trade"],
    "message": "ok"
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `success` | bool | 是否成功 |
| `latency_ms` | int | 往返时间 |
| `permissions` | string[] \| null | adapter 尝试读取 key 权限；失败时 null |
| `message` | string | 失败时的中文错误映射（错误码 → 中文） |

失败时 HTTP 400：

```json
{"code": 40005, "message": "交易所 API Key/Secret 无效", "detail": {"exchange": "binance"}}
```

---

### 3.9 GET `/accounts/{account_id}/balance` 实时余额

**响应**（CCXT `fetch_balance` 归一化结构）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "free": {"USDT": 10000.0, "BTC": 0.5},
    "used": {"USDT": 200.0},
    "total": {"USDT": 10200.0, "BTC": 0.5},
    "timestamp": 1755164520301
  }
}
```

连接失败 → 400 `连接交易所失败`。

---

### 3.10 GET `/accounts/{account_id}/snapshots` 资产快照历史

**查询参数**：`limit`（默认 100，范围 1~500）。

**响应**：按 `snapshot_at` 倒序。

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "uuid",
      "account_id": "uuid",
      "total_usd": 50000.0,
      "balances": {
        "BTC": {"free": 0.5, "used": 0, "total": 0.5, "usd": 30000},
        "USDT": {"free": 20000, "used": 0, "total": 20000, "usd": 20000}
      },
      "snapshot_at": "2026-08-14T09:00:00+00:00"
    }
  ]
}
```

前端资产折线图：按 `snapshot_at` 描点，Y 轴 `total_usd`。

---

### 3.11 POST `/accounts/{account_id}/sync` 触发同步

**说明**：异步触发 Celery task `sync_trades`（交易记录） + `sync_asset_snapshot`（资产快照）。

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "account_id": "uuid",
    "task_id": "celery-task-uuid",
    "message": "同步任务已触发"
  }
}
```

若 Celery/Redis 未启动（开发环境）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": null,
    "message": "同步任务排队失败，请检查 Celery 服务"
  }
}
```

**自动调度**：Celery Beat 每 15 分钟触发 `sync_all_accounts`（仅 `is_enabled=true` 且 `status=active`），每小时记录资产快照。

---

## 4. 错误示例速查

| 场景 | HTTP | code | message |
|---|---|---|---|
| exchange 不在受支持列表 | 400 | 40000 | 不支持的交易所 |
| OKX/Coinbase 缺少 passphrase | 400 | 40000 | OKX / Coinbase 必填 passphrase |
| 每用户账号数 > 5 | 400 | 40000 | 最多创建 5 个交易所账号 |
| 连接测试失败 | 400 | 40005 | 交易所 API Key/Secret 无效 |
| 删除账号含近 30 天交易 | 400 | 40006 | 该账号有近 30 天的关联交易记录，无法删除 |
| Viewer 发起写操作 | 403 | 40301 | Viewer 角色不允许写操作 |
| 提现/划转接口 | 403 | 40302 | 提币/资金划转功能在 V1 已禁用 |
| 账号 ID 不存在 | 404 | 40400 | 账号不存在 |
