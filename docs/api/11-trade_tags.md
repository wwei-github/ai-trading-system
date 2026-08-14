# 交易标签接口

> **模块前缀**: `/trade-tags` ｜ **RBAC**: Viewer 只读 / Trader & Admin 写操作（`reject_viewer_write`）
> **唯一约束**：`trade_tags.user_id + name`（同一用户下标签名不可重复）
> **使用计数**：`usage_count` 冗余字段，由 `trade_service._incr_tag_usage` 在交易创建/标签更新时递增；合并时由 `merge_tags` 回写。

所有端点需 `Authorization: Bearer <access_token>`。

---

## 1. 端点清单

| # | 方法 | 路径 | 功能 | 权限 |
|---|---|---|---|---|
| 1 | GET | `/trade-tags` | 标签列表（按使用次数降序 + 名称升序） | 登录 |
| 2 | POST | `/trade-tags` | 创建标签（user_id + name 唯一约束） | Trader / Admin |
| 3 | PATCH | `/trade-tags/{tag_id}` | 更新标签名 / 颜色（改 name 需检查唯一） | Trader / Admin |
| 4 | DELETE | `/trade-tags/{tag_id}` | 删除标签（同步从所有交易 tags 数组中移除） | Trader / Admin |
| 5 | POST | `/trade-tags/merge` | 合并标签（源标签 → 目标标签；源被删除） | Trader / Admin |

---

## 2. 公共数据模型

### 2.1 TradeTagResponse（返回）

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "趋势",
  "color": "#1890ff",
  "usage_count": 42,
  "created_at": "2026-08-01T12:00:00+00:00",
  "updated_at": "2026-08-14T10:00:00+00:00"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | 主键 |
| `user_id` | uuid | 所属用户；不同用户间标签完全隔离 |
| `name` | string(≤50) | 标签名；用户唯一 |
| `color` | string(≤20) | HEX 颜色；默认 `#1890ff`（Ant Design 主色） |
| `usage_count` | int | 使用次数（冗余）；**只增不减**（删除交易/标签不回退，仅在合并时累加）。用于渲染标签云/排序。 |

### 2.2 标签与交易记录的关系

- 交易记录的 `tags` 字段使用 JSONB 数组存**标签名**（字符串数组），而不是 tag ID。
- 这是故意的设计：
  1. 筛选时 Postgres JSONB `@>` 操作符原生支持字符串数组匹配（不需要 JOIN）。
  2. `merge_tags` 时只需更新 `tags` 数组的字符串值，无需改引用。
- 副作用：**标签改名不会自动反映到交易记录**。若需要"改名 → 历史交易全部同步改名"，在 `PATCH /trade-tags/{id}` 中 `name` 变更时可手动对同用户的交易遍历替换（当前服务**未自动做**，以避免改名触发大规模 UPDATE；默认行为是"改名后新交易使用新名，旧交易保留旧名"）。

---

## 3. 接口详情

### 3.1 GET `/trade-tags` 列表

**请求参数**：无。按 `usage_count desc, name asc` 返回该用户全部标签。

**响应**：`TradeTagResponse[]` 数组。

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {"id": "...", "name": "趋势", "color": "#1890ff", "usage_count": 42},
    {"id": "...", "name": "网格", "color": "#52c41a", "usage_count": 18},
    {"id": "...", "name": "套利", "color": "#722ed1", "usage_count": 3}
  ]
}
```

---

### 3.2 POST `/trade-tags` 创建标签

**请求体 `TradeTagCreate`**：

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `name` | ✅ | string（1~50） | 标签名；同用户下若已存在 → 409 |
| `color` | — | string（≤20） | HEX 颜色；默认 `#1890ff` |

**成功响应**：`TradeTagResponse`。

**失败 409（冲突）**：

```json
{
  "code": 40900,
  "message": "标签 '趋势' 已存在",
  "detail": {"name": "趋势"}
}
```

> 注意：`trade_service.create_trade` / `update_trade_tags` 中若传入的标签不存在会**懒创建**（`_incr_tag_usage`：找不到则 `TradeTag(name=tag, usage_count=1)`）。
> 因此前端不强制先调此接口，也可直接在交易中直接写标签字符串。显式创建的好处是可**预先指定颜色**。

---

### 3.3 PATCH `/trade-tags/{tag_id}` 更新标签

**请求体 `TradeTagUpdate`**（两字段均可选）：

```json
{"name": "新趋势", "color": "#f5222d"}
```

| 字段 | 约束 |
|---|---|
| `name` | 若改变且与同用户其他标签冲突 → 409 |
| `color` | 任意 HEX 字符串（服务端不额外校验格式） |

**注意**（同 §2.2）：修改 `name` **不会**自动批量更新历史交易的 `tags` 数组。如需同步，可：
1. 先 `/merge`（源=旧标签名对应的旧 tag；目标=新 tag_id）；或
2. 前端自行执行批量 `PATCH /trades/{id}/tags`。

**响应**：`TradeTagResponse`；找不到 → 404。

---

### 3.4 DELETE `/trade-tags/{tag_id}` 删除标签

**语义**：
1. 将当前用户下所有引用该标签名的交易 `tags` 数组中**移除该字符串**（`[t for t in tags if t != name]`）。
2. 删除 `trade_tags` 行。

**响应**：

```json
{"code": 0, "message": "ok", "data": {"deleted": true}}
```

找不到 → 404。

> 警告：交易量很大时此操作可能较耗时（当前应用层循环遍历；未做批量 UPDATE）。生产环境建议改为 PostgreSQL `UPDATE trades SET tags = tags - '标签名' WHERE ...`。

---

### 3.5 POST `/trade-tags/merge` 合并标签

**典型场景**：用户对同含义建了多个别名（如"趋势"/"趋势交易"/"Trend"），想统一成一个。

**请求体 `TradeTagMergeRequest`**：

```json
{
  "source_tag_ids": ["uuid-A", "uuid-B"],
  "target_tag_id": "uuid-C"
}
```

| 字段 | 约束 |
|---|---|
| `source_tag_ids` | 数组，长度 ≥1；不能包含 `target_tag_id` |
| `target_tag_id` | 单个 ID；必须存在 |

**处理流程（`TradeTagService.merge_tags`）**：

1. 校验：`target_id` 存在且不在 `sources`；每个 source 存在且属同一用户。
2. 加载所有源标签名 → `source_names = [t.name for t in sources]`。
3. 查询当前用户所有交易，其 `tags` 数组 `@>` 任一源标签名。
4. 对每条交易做映射：**若标签 ∈ source_names → 替换为 target_name（若新名未已存在）**；其他标签保留。去重。
5. `target_tag.usage_count += updated_trades`。
6. 源标签全部 `DELETE`。

**响应 `TradeTagMergeResponse`**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "merged_count": 2,
    "updated_trades": 17,
    "deleted_tags": 2
  }
}
```

| 字段 | 说明 |
|---|---|
| `merged_count` | 被合并的源标签数量（=len(source_tag_ids)） |
| `updated_trades` | 受影响的交易数（tags 数组被改写的行数） |
| `deleted_tags` | 被删除的源标签行数（= merged_count） |

**失败示例**：

- target_tag_id 在 source_tag_ids 中 → 400 `目标标签不能在源标签列表中`。
- source_tag_ids 中存在不存在 ID → 404 `源标签不存在`。
- target 不存在 → 404 `目标标签不存在`。

---

## 4. 错误示例速查

| 场景 | HTTP | code | message |
|---|---|---|---|
| 创建标签 name 重复 | 409 | 40900 | 标签 'xxx' 已存在 |
| 修改 name 时冲突 | 409 | 40900 | 标签 'xxx' 已存在 |
| merge 目标在源中 | 400 | 40000 | 目标标签不能在源标签列表中 |
| merge 源/目标不存在 | 404 | 40400 | 源/目标标签不存在（含 detail.tag_id） |
| 标签 ID 不存在 | 404 | 40400 | 标签不存在 |
| Viewer 发起写操作 | 403 | 40301 | Viewer 角色不允许写操作 |
