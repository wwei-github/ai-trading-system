# 统计分析接口

> **模块前缀**: `/statistics` ｜ **RBAC**: 登录可见本人；`/team-overview` 仅 Admin
> **数据源**: `Trade.pnl` 真实盈亏字段（Stage 3 引擎写入）；`AssetSnapshot` 资产快照表
> **缓存**: Redis 30s（key 含 user_id + 参数哈希；Redis 不可用时自动降级直查）

所有端点需 `Authorization: Bearer <access_token>`。

---

## 1. 端点清单

### 1.1 Stage 4 新端点（推荐）

| # | 方法 | 路径 | 功能 | 权限 |
|---|---|---|---|---|
| 1 | GET | `/statistics/health` | 模块健康检查 | 登录 |
| 2 | GET | `/statistics/metrics` | 14 项核心指标 | 登录 |
| 3 | GET | `/statistics/equity-curve` | 权益曲线（按日累计） | 登录 |
| 4 | GET | `/statistics/monthly-pnl` | 月度盈亏柱状图 | 登录 |
| 5 | GET | `/statistics/pnl-distribution` | 盈亏分布直方图 | 登录 |
| 6 | GET | `/statistics/symbol-contribution` | 币种贡献度饼图 | 登录 |
| 7 | GET | `/statistics/strategy-contribution` | 策略贡献度柱状图 | 登录 |
| 8 | GET | `/statistics/heatmap` | 星期×小时热力图 | 登录 |
| 9 | GET | `/statistics/asset-composition` | 资产构成饼图（最近快照） | 登录 |
| 10 | GET | `/statistics/drawdown-curve` | 回撤曲线 | 登录 |
| 11 | GET | `/statistics/pnl-scatter` | 每笔盈亏散点 | 登录 |
| 12 | GET | `/statistics/report` | 统计报表（5 章 JSON） | 登录 |
| 13 | GET | `/statistics/team-overview` | 团队视角聚合 | **Admin** |
| 14 | GET | `/statistics/export` | CSV 导出 | 登录 |

### 1.2 兼容旧端点（保留向后兼容）

| # | 方法 | 路径 | 功能 |
|---|---|---|---|
| 15 | GET | `/statistics/summary` | 交易汇总（映射到 CoreMetrics 子集） |
| 16 | GET | `/statistics/pnl` | 按周期盈亏（daily/weekly/monthly） |
| 17 | GET | `/statistics/coins` | 币种维度统计（映射到 symbol-contribution） |
| 18 | GET | `/statistics/asset-trend` | 资产趋势面积图 |
| 19 | GET | `/statistics/exchange-distribution` | 按交易所分布 |
| 20 | GET | `/statistics/side-distribution` | 买卖方向分布 |
| 21 | GET | `/statistics/time-distribution` | 按小时分布 |
| 22 | GET | `/statistics/strategy-comparison` | 策略收益对比 |
| 23 | GET | `/statistics/monthly-report` | 月度报表 |

---

## 2. 公共查询参数（5 维过滤 + 时间）

所有 Stage 4 新端点（除 `/health`、`/asset-composition`、`/team-overview` 外）支持以下公共查询参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `account_id` | uuid | — | 账号筛选 |
| `strategy_id` | uuid | — | 策略筛选 |
| `symbol` | string | — | 交易对精确匹配（CCXT 风格 `BTC/USDT`） |
| `side` | enum | — | `buy` / `sell` |
| `tags` | string[]（重复 query） | — | 标签包含；Postgres `tags @> ['a','b']`（AND 包含） |
| `start_date` | datetime | — | `executed_at >=`（ISO 8601，含时区） |
| `end_date` | datetime | — | `executed_at <=`（ISO 8601，含时区） |
| `period_preset` | enum | — | 快捷预设：`today`/`week`/`month`/`quarter`/`year`/`all`；与 `start_date`/`end_date` 二选一，同时传则预设被忽略 |

> **过滤口径对齐 PRD §5.4.1 R1**：5 维（账号 / 策略 / 标签 / 币种 / 方向）+ 时间范围（区间或快捷预设）。

---

## 3. 数据模型

### 3.1 CoreMetrics（14 项核心指标）

| # | 字段 | 类型 | 口径 |
|---|---|---|---|
| 1 | `total_pnl` | Decimal | `SUM(trade.pnl)` |
| 2 | `total_return_rate` | Decimal \| null | `总盈亏 / 期初资产`（无快照则用首次买入成本估算） |
| 3 | `total_volume` | Decimal | `SUM(price * quantity)` |
| 4 | `total_fee` | Decimal | `SUM(fee)` |
| 5 | `total_trades` | int | `COUNT(*)` |
| 6 | `buy_count` | int | `SUM(CASE WHEN side='buy' THEN 1 ELSE 0 END)` |
| 7 | `sell_count` | int | `SUM(CASE WHEN side='sell' THEN 1 ELSE 0 END)` |
| 8 | `win_rate` | Decimal \| null | `COUNT(pnl>0) / COUNT(pnl IS NOT NULL)` |
| 9 | `avg_win_loss_ratio` | Decimal \| null | `AVG(盈利单 pnl) / |AVG(亏损单 pnl)|` |
| 10 | `profit_count` | int | `COUNT(pnl>0)` |
| 11 | `loss_count` | int | `COUNT(pnl<0)` |
| 12 | `max_drawdown` | Decimal \| null | `max((peak - equity) / peak)` 滚动窗口（基于日累计 pnl） |
| 13 | `sharpe_ratio` | Decimal \| null | `AVG(daily_pnl) / STDDEV(daily_pnl) * sqrt(365)` |
| 14 | `sortino_ratio` | Decimal \| null | `AVG(daily_pnl) / STDDEV(daily_pnl<0) * sqrt(365)` |
| - | `max_single_profit` | Decimal \| null | `MAX(pnl)` |
| - | `max_single_loss` | Decimal \| null | `MIN(pnl)` |
| - | `avg_holding_seconds` | int \| null | `AVG(holding_seconds)`（仅平仓单） |

**示例响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "total_pnl": "1234.56",
    "total_return_rate": "0.1221",
    "total_volume": "10100.00000000",
    "total_fee": "10.00000000",
    "total_trades": 2,
    "buy_count": 1,
    "sell_count": 1,
    "win_rate": "0.65",
    "avg_win_loss_ratio": "1.85",
    "profit_count": 13,
    "loss_count": 7,
    "max_drawdown": "0.18",
    "sharpe_ratio": "2.34",
    "sortino_ratio": "3.12",
    "max_single_profit": "500.00",
    "max_single_loss": "-200.00",
    "avg_holding_seconds": 86400
  }
}
```

### 3.2 9 类图表数据模型

| 图表 | 数据模型 | 关键字段 |
|---|---|---|
| 权益曲线 | `EquityCurvePoint` | `date`/`equity`/`cum_pnl`/`benchmark?` |
| 月度盈亏 | `MonthlyPnLBar` | `month`(YYYY-MM)/`pnl`/`trade_count` |
| 盈亏分布 | `PnLDistributionBin` | `bin_start`/`bin_end`/`count` |
| 币种贡献 | `SymbolContribution` | `symbol`/`pnl`/`trade_count`/`percentage` |
| 策略贡献 | `StrategyContribution` | `strategy_id`/`strategy_name?`/`pnl`/`trade_count` |
| 热力图 | `HeatmapCell` | `weekday`(0=周一..6=周日)/`hour`(0-23)/`trade_count`/`pnl` |
| 资产构成 | `AssetComposition` | `symbol`/`total`/`usd_value`/`percentage` |
| 回撤曲线 | `DrawdownPoint` | `date`/`drawdown` |
| 盈亏散点 | `ScatterPoint` | `trade_id`/`pnl`/`holding_seconds?`/`symbol`（上限 500 点） |

---

## 4. 接口详情

### 4.1 GET `/statistics/health` 健康检查

无参数。

**响应**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {"status": "ok", "module": "statistics"}
}
```

---

### 4.2 GET `/statistics/metrics` 14 项核心指标

**查询参数**：见 [§2 公共查询参数](#2-公共查询参数5-维过滤--时间)

**响应**：`ApiResponse<CoreMetrics>`，见 [§3.1](#31-coremetrics14-项核心指标)

---

### 4.3 GET `/statistics/equity-curve` 权益曲线

按日聚合 pnl，返回累计权益曲线（折线图）。

**查询参数**：公共查询参数（无 `tags`）

**响应**：`ApiResponse<EquityCurvePoint[]>`

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {"date": "2026-08-01", "equity": "100.00", "cum_pnl": "100.00", "benchmark": null},
    {"date": "2026-08-02", "equity": "250.00", "cum_pnl": "250.00", "benchmark": null}
  ]
}
```

> **说明**：无资产快照时 `equity = cum_pnl`；有快照时后续版本将叠加期初资产 + benchmark（BTC/ETH 基准）。

---

### 4.4 GET `/statistics/monthly-pnl` 月度盈亏柱状图

**查询参数**：公共查询参数（无 `tags`）

**响应**：`ApiResponse<MonthlyPnLBar[]>`

```json
{
  "data": [
    {"month": "2026-07", "pnl": "1200.00", "trade_count": 15},
    {"month": "2026-08", "pnl": "-300.00", "trade_count": 8}
  ]
}
```

---

### 4.5 GET `/statistics/pnl-distribution` 盈亏分布直方图

**查询参数**：

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| （公共） | | | 见 §2 |
| `bin_count` | int | 10 | 分桶数量（5~50）；Postgres `width_bucket` |

**响应**：`ApiResponse<PnLDistributionBin[]>`

```json
{
  "data": [
    {"bin_start": "-500.00", "bin_end": "-250.00", "count": 3},
    {"bin_start": "-250.00", "bin_end": "0.00", "count": 7},
    {"bin_start": "0.00", "bin_end": "250.00", "count": 12}
  ]
}
```

---

### 4.6 GET `/statistics/symbol-contribution` 币种贡献度饼图

按 `symbol` GROUP BY pnl，计算占总盈亏比例。

**查询参数**：公共查询参数（无 `tags`）

**响应**：`ApiResponse<SymbolContribution[]>`（按 pnl 降序）

```json
{
  "data": [
    {"symbol": "BTC/USDT", "pnl": "1500.00", "trade_count": 20, "percentage": "0.65"},
    {"symbol": "ETH/USDT", "pnl": "800.00", "trade_count": 10, "percentage": "0.35"}
  ]
}
```

---

### 4.7 GET `/statistics/strategy-contribution` 策略贡献度柱状图

仅含 `strategy_id` 非空的交易，JOIN `strategies` 表填充策略名。

**查询参数**：公共查询参数（无 `tags`）

**响应**：`ApiResponse<StrategyContribution[]>`

```json
{
  "data": [
    {"strategy_id": "uuid", "strategy_name": "网格策略", "pnl": "1500.00", "trade_count": 20},
    {"strategy_id": "uuid", "strategy_name": "趋势跟踪", "pnl": "-200.00", "trade_count": 5}
  ]
}
```

---

### 4.8 GET `/statistics/heatmap` 星期×小时热力图

按 `isodow`(1=周一..7=周日)-1 与 `hour`(0-23) 双维聚合。

**查询参数**：公共查询参数（无 `tags`/`side`/`strategy_id`）

**响应**：`ApiResponse<HeatmapCell[]>`

```json
{
  "data": [
    {"weekday": 0, "hour": 9, "trade_count": 5, "pnl": "200.00"},
    {"weekday": 0, "hour": 14, "trade_count": 8, "pnl": "-50.00"}
  ]
}
```

---

### 4.9 GET `/statistics/asset-composition` 资产构成饼图（最近快照）

基于 `asset_snapshots` 表最近一条快照的 `balances` 字段（JSONB），按币种聚合 USD 占比。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `account_id` | uuid | — | 按账号筛选快照 |

**响应**：`ApiResponse<AssetComposition[]>`（按 usd_value 降序）

```json
{
  "data": [
    {"symbol": "USDT", "total": "10000.00", "usd_value": "10000.00", "percentage": "0.65"},
    {"symbol": "BTC", "total": "0.5", "usd_value": "5000.00", "percentage": "0.35"}
  ]
}
```

> 无快照时返回空数组 `[]`。

---

### 4.10 GET `/statistics/drawdown-curve` 回撤曲线

基于权益曲线的滚动 peak 计算 `drawdown = (peak - equity) / peak`。

**查询参数**：公共查询参数（无 `tags`）

**响应**：`ApiResponse<DrawdownPoint[]>`

```json
{
  "data": [
    {"date": "2026-08-01", "drawdown": "0.00"},
    {"date": "2026-08-02", "drawdown": "0.15"}
  ]
}
```

---

### 4.11 GET `/statistics/pnl-scatter` 每笔盈亏散点

返回 `pnl` vs `holding_seconds` 散点（最多 500 点，按 `executed_at` 升序）。

**查询参数**：公共查询参数（无 `tags`/`side`/`strategy_id`）

**响应**：`ApiResponse<ScatterPoint[]>`

```json
{
  "data": [
    {"trade_id": "uuid", "pnl": "200.00", "holding_seconds": 3600, "symbol": "BTC/USDT"},
    {"trade_id": "uuid", "pnl": "-50.00", "holding_seconds": 7200, "symbol": "ETH/USDT"}
  ]
}
```

---

### 4.12 GET `/statistics/report` 统计报表（5 章 JSON）

一次性聚合所有指标 + 9 类图表 + Top10 盈亏明细，用于前端报表导出。

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| （公共） | | | 见 §2 |
| `title` | string | — | 报表标题（默认"AI 交易系统统计报表"） |

**响应**：`ApiResponse<StatisticsReport>`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "cover": {
      "title": "AI 交易系统统计报表",
      "user_id": "uuid",
      "period_start": "2026-01-01T00:00:00Z",
      "period_end": "2026-08-14T10:00:00Z",
      "generated_at": "2026-08-14T10:00:00Z",
      "summary_text": "周期：2026-01-01 至 2026-08-14；总交易 50 笔；总盈亏 1234.56；胜率 0.65"
    },
    "metrics": {"metrics": { /* CoreMetrics */ }},
    "charts": {
      "equity_curve": [ /* EquityCurvePoint[] */ ],
      "monthly_pnl": [ /* MonthlyPnLBar[] */ ],
      "pnl_distribution": [ /* PnLDistributionBin[] */ ],
      "symbol_contribution": [ /* SymbolContribution[] */ ],
      "strategy_contribution": [ /* StrategyContribution[] */ ],
      "heatmap": [ /* HeatmapCell[] */ ],
      "asset_composition": [ /* AssetComposition[] */ ],
      "drawdown_curve": [ /* DrawdownPoint[] */ ],
      "pnl_scatter": [ /* ScatterPoint[] */ ]
    },
    "top_trades": {
      "top_profits": [
        {"id":"uuid","symbol":"BTC/USDT","side":"sell","price":"51000","quantity":"0.1","pnl":"500.00","pnl_ratio":"0.1","executed_at":"...","holding_seconds":3600}
      ],
      "top_losses": [
        {"id":"uuid","symbol":"ETH/USDT","side":"sell","price":"3000","quantity":"1","pnl":"-200.00","pnl_ratio":"-0.07","executed_at":"...","holding_seconds":7200}
      ]
    },
    "ai_conclusion": {
      "conclusion": "（V1 占位：AI 总结将在 V1.3 接入 LLM 后生成）",
      "suggestions": []
    }
  }
}
```

> **5 章结构对齐 PRD §5.4.4**：封面 / 核心指标 / 图表 / Top10 盈亏 / AI 总结（V1 占位）。

---

### 4.13 GET `/statistics/team-overview` 团队视角聚合（Admin）

按 `user_id` GROUP BY，返回所有团队成员的盈亏汇总。

**RBAC**: 仅 `admin` 角色可访问；Trader/Viewer → 403

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `strategy_id` | uuid | — | 策略筛选 |
| `symbol` | string | — | 币种筛选 |
| `start_date` | datetime | — | `executed_at >=` |
| `end_date` | datetime | — | `executed_at <=` |
| `period_preset` | enum | — | 快捷预设 |

**响应**：`ApiResponse<TeamOverview>`

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "member_count": 3,
    "total_pnl": "5000.00",
    "total_trades": 150,
    "members": [
      {
        "user_id": "uuid",
        "user_email": "trader1@example.com",
        "user_nickname": "Trader1",
        "role": "trader",
        "total_pnl": "3000.00",
        "total_trades": 80,
        "win_rate": "0.65"
      },
      {
        "user_id": "uuid",
        "user_email": "trader2@example.com",
        "user_nickname": "Trader2",
        "role": "trader",
        "total_pnl": "2000.00",
        "total_trades": 70,
        "win_rate": "0.55"
      }
    ]
  }
}
```

> `members` 按 `total_pnl` 降序排列。

---

### 4.14 GET `/statistics/export` CSV 导出

**查询参数**：`start_date` / `end_date` / `symbol`

**响应**：`text/csv; charset=utf-8`，含以下章节：

- `# 交易汇总`：总交易笔数 / 总成交额 / 总手续费 / 买入笔数 / 卖出笔数 / 胜率 / 盈亏
- `# 按周期盈亏`：周期 / 盈亏 / 交易笔数
- `# 币种统计`：交易对 / 交易笔数 / 净盈亏
- `# 资产趋势`：日期 / 总资产(USD)

**响应头**：`Content-Disposition: attachment; filename=statistics_report.csv`

---

## 5. 兼容旧端点详情

### 5.1 GET `/statistics/summary` 交易汇总

**查询参数**：`start_date` / `end_date` / `symbol`

**响应**：`ApiResponse<TradeSummary>`

```json
{
  "data": {
    "total_trades": 50,
    "total_volume": "10100.00000000",
    "total_fee": "10.00000000",
    "buy_count": 25,
    "sell_count": 25,
    "win_rate": "0.65",
    "profit_loss": "1234.56"
  }
}
```

### 5.2 GET `/statistics/pnl` 按周期盈亏

**查询参数**：`period`(daily/weekly/monthly，默认 daily) / `start_date` / `end_date` / `symbol`

**响应**：`ApiResponse<PnLByPeriod[]>`

```json
{
  "data": [
    {"period": "2026-08-01", "pnl": "100.00", "trade_count": 5},
    {"period": "2026-08-02", "pnl": "-50.00", "trade_count": 3}
  ]
}
```

### 5.3 GET `/statistics/coins` 币种统计

**查询参数**：`start_date` / `end_date` / `symbol`

**响应**：`ApiResponse<CoinStat[]>`（映射自 symbol-contribution）

### 5.4 GET `/statistics/asset-trend` 资产趋势

**查询参数**：`account_id` / `days`(1~365，默认 30)

**响应**：`ApiResponse<AssetTrend[]>`

### 5.5-5.8 其他兼容端点

- `/exchange-distribution`：按交易所 GROUP BY
- `/side-distribution`：按 buy/sell GROUP BY
- `/time-distribution`：按 hour(0-23) GROUP BY
- `/strategy-comparison`：策略收益对比（映射自 strategy-contribution）

### 5.9 GET `/statistics/monthly-report` 月度报表

**查询参数**：`year` / `month`(1-12)

**响应**：`{year, month, summary, daily_pnl[], coin_stats[]}`

---

## 6. 缓存策略

| 维度 | 说明 |
|---|---|
| Key 格式 | `stats:v1:{endpoint}:{user_id}:{hash(params)}` |
| TTL | 30 秒 |
| 降级 | Redis 不可用时自动跳过缓存直查 DB（不影响业务） |
| 失效 | 数据变更后等待 TTL 自然过期；高频写场景可手动 `DEL` |

---

## 7. 计算口径说明

### 7.1 盈亏数据来源

所有统计基于 `Trade.pnl` 字段（Stage 3 盈亏引擎写入）：
- **现货**：FIFO 配对，卖出 trade 写入 `pnl = (sell-buy)*qty - 摊销手续费`
- **合约**：平仓 trade 写入 `pnl`，含杠杆乘数
- 买入/未平仓 trade 的 `pnl = NULL`，不计入胜率/盈亏比，但计入成交额

### 7.2 风险指标计算

- **最大回撤**：基于日累计 pnl 序列，滚动 peak 计算 `(peak - equity) / peak`
- **夏普比率**：`AVG(daily_pnl) / STDDEV(daily_pnl) * sqrt(365)`（年化）
- **Sortino**：`AVG(daily_pnl) / STDDEV(daily_pnl<0) * sqrt(365)`（仅负收益标准差）

> 数据点 < 2 天时风险指标返回 `null`。

### 7.3 时区与精度

- 所有时间存储 UTC，查询参数支持 ISO 8601 含时区格式
- 金额使用 `Decimal`（PostgreSQL `NUMERIC(20,8)`），避免浮点累计误差
- 百分比返回小数形式（`0.65` 表示 65%），前端按需 ×100 显示
