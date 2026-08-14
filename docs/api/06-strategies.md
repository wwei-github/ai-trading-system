# 06-策略管理接口文档（Stage 6）

> 模块：策略系统 - DSL + 模板 + 回测 + 模拟交易 + 实盘半自动
> 对齐 PRD：§5.6.1 ~ §5.6.5、§9.2（风控八阈值）
> Base URL：`/api/v1/strategies`

---

## 目录

1. [策略 CRUD](#1-策略-crud)
2. [策略克隆](#2-策略克隆)
3. [回测管理](#3-回测管理)
4. [回测对比](#4-回测对比)
5. [模拟交易](#5-模拟交易)
6. [实盘半自动交易](#6-实盘半自动交易)
7. [SSE 实时推送](#7-sse-实时推送)
8. [风控八阈值](#8-风控八阈值)
9. [策略 DSL 结构](#9-策略-dsl-结构)

---

## 1. 策略 CRUD

### 1.1 获取策略列表

```
GET /strategies?include_templates=true
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| include_templates | boolean | 否 | 是否包含内置模板，默认 true |

**返回结果：**

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "name": "双均线金叉死叉（模板）",
      "category": "trend",
      "description": "基于快慢均线交叉的趋势追踪策略",
      "rules": { /* DSL 结构 */ },
      "params": { "fast_period": 5, "slow_period": 20 },
      "source_book_id": null,
      "status": "active",
      "is_template": true,
      "created_at": "2026-08-14T10:00:00Z",
      "updated_at": "2026-08-14T10:00:00Z"
    }
  ]
}
```

### 1.2 创建策略

```
POST /strategies
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 策略名称 |
| category | string | 是 | 策略类别（trend / mean_reversion / breakout / ...） |
| description | string | 否 | 描述 |
| rules | object | 否 | 策略 DSL（结构见 §9） |
| params | object | 否 | 策略参数 |
| source_book_id | uuid | 否 | 来源书籍 ID |

### 1.3 获取策略详情

```
GET /strategies/{strategy_id}
```

### 1.4 更新策略

```
PATCH /strategies/{strategy_id}
```

> 内置模板策略（`is_template=true`）不可编辑，需先克隆。

### 1.5 删除策略

```
DELETE /strategies/{strategy_id}
```

> 内置模板策略不可删除。

---

## 2. 策略克隆

### 2.1 克隆策略

```
POST /strategies/{strategy_id}/clone
```

**请求体（可选）：**

```json
{
  "new_name": "我的双均线策略"
}
```

**返回结果：** 新策略对象（`is_template=false`，`status=draft`，可自由编辑）。

---

## 3. 回测管理

### 3.1 触发策略回测

```
POST /strategies/{strategy_id}/backtest
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 交易对，如 `BTC/USDT` |
| timeframe | string | 否 | K 线周期，默认 `1d` |
| start_date | date | 是 | 开始日期 `2025-01-01` |
| end_date | date | 是 | 结束日期 |
| initial_capital | decimal | 否 | 初始资金，默认 10000.00 |
| params | object | 否 | 回测参数覆盖（如 `fee_rate`、`slippage`） |

**返回结果：** 回测记录（`status=pending`），通过 SSE 订阅进度。

### 3.2 获取回测历史

```
GET /strategies/{strategy_id}/backtests
```

### 3.3 获取回测详情

```
GET /strategies/backtests/{backtest_id}
```

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "strategy_id": "uuid",
    "symbol": "BTC/USDT",
    "timeframe": "1d",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "initial_capital": "10000.00",
    "params": { "fee_rate": 0.001 },
    "result": {
      "metrics": {
        "total_return": 0.2345,
        "annual_return": 0.2345,
        "max_drawdown": -0.1234,
        "sharpe_ratio": 1.56,
        "sortino_ratio": 2.1,
        "win_rate": 0.55,
        "profit_loss_ratio": 1.8,
        "trade_count": 25,
        "profit_count": 14,
        "loss_count": 11,
        "max_single_profit": 500.5,
        "max_single_loss": -300.2,
        "avg_holding_bars": 15,
        "final_value": 12345.0,
        "buy_hold_return": 0.15,
        "volatility": 0.25
      },
      "equity_curve": [
        { "timestamp": "2025-01-01T00:00:00Z", "nav": 10000.0, "buy_hold": 10000.0 }
      ],
      "drawdown_curve": [
        { "timestamp": "2025-01-01T00:00:00Z", "drawdown": 0.0 }
      ],
      "trades": [ /* 交易明细 */ ],
      "bars": 365,
      "start_date": "2025-01-01T00:00:00Z",
      "end_date": "2025-12-31T00:00:00Z"
    },
    "status": "completed",
    "created_at": "2026-08-14T10:00:00Z",
    "updated_at": "2026-08-14T10:00:05Z"
  }
}
```

### 3.4 获取回测交易明细

```
GET /strategies/backtests/{backtest_id}/trades?limit=100&offset=0
```

| 参数 | 类型 | 说明 |
|------|------|------|
| limit | int | 每页数量（1-500），默认 100 |
| offset | int | 偏移量，默认 0 |

**返回结果：**

```json
{
  "code": 0,
  "data": [
    {
      "id": "uuid",
      "backtest_id": "uuid",
      "strategy_id": "uuid",
      "symbol": "BTC/USDT",
      "side": "long",
      "entry_time": "2025-01-15T00:00:00Z",
      "entry_price": 42000.5,
      "quantity": 0.235,
      "exit_time": "2025-02-10T00:00:00Z",
      "exit_price": 45000.0,
      "pnl": 682.5,
      "pnl_pct": 0.068,
      "holding_bars": 25,
      "exit_reason": "signal",
      "created_at": "2026-08-14T10:00:05Z"
    }
  ]
}
```

---

## 4. 回测对比

### 4.1 对比两次回测

```
POST /strategies/backtests/compare
```

**请求体：**

```json
{
  "backtest_id_a": "uuid",
  "backtest_id_b": "uuid"
}
```

> 仅可对比已完成的回测（`status=completed`）。

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "metrics_a": { /* 回测 A 指标 */ },
    "metrics_b": { /* 回测 B 指标 */ },
    "metrics_diff": {
      "total_return": 0.05,
      "max_drawdown": 0.02,
      "sharpe_ratio": 0.3
    },
    "equity_curve_combined": [
      { "timestamp": "2025-01-01T00:00:00Z", "nav_a": 10000, "nav_b": 10000 }
    ]
  }
}
```

---

## 5. 模拟交易

### 5.1 启动模拟交易

```
POST /strategies/paper-trading
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| strategy_id | uuid | 是 | 策略 ID |
| symbol | string | 是 | 交易对，如 `BTC/USDT` |
| timeframe | string | 否 | K 线周期，默认 `1h` |
| initial_capital | float | 否 | 初始虚拟资金，默认 10000.0 |

> 每策略+每币种仅允许一个 running 状态的模拟账号。

### 5.2 获取模拟交易列表

```
GET /strategies/paper-trading?status=running
```

### 5.3 获取模拟交易详情

```
GET /strategies/paper-trading/{paper_account_id}
```

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "user_id": "uuid",
    "strategy_id": "uuid",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "initial_capital": "10000.00",
    "current_equity": "10500.00",
    "available_cash": "5000.00",
    "position": 0.12,
    "avg_entry_price": 42000.0,
    "status": "running",
    "total_trades": 15,
    "total_pnl": "500.00",
    "started_at": "2026-08-14T10:00:00Z",
    "stopped_at": null
  }
}
```

### 5.4 控制模拟交易

```
POST /strategies/paper-trading/{paper_account_id}/control
```

**请求体：**

```json
{
  "action": "pause"  // pause / resume / stop
}
```

### 5.5 获取模拟交易记录

```
GET /strategies/paper-trading/{paper_account_id}/trades?limit=100&offset=0
```

---

## 6. 实盘半自动交易

### 6.1 启动实盘策略实例

```
POST /strategies/live-trading
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| strategy_id | uuid | 是 | 策略 ID |
| account_id | uuid | 是 | 交易所账号 ID |
| symbol | string | 是 | 交易对 |
| timeframe | string | 否 | K 线周期，默认 `1h` |
| mode | string | 否 | 运行模式：`semi_auto`（默认）/ `full_auto`（V2） |
| risk_params | object | 否 | 风控参数覆盖（见 §8） |

### 6.2 获取实盘策略实例列表

```
GET /strategies/live-trading?status=running
```

### 6.3 获取实盘策略实例详情

```
GET /strategies/live-trading/{instance_id}
```

### 6.4 暂停 / 恢复 / 停止

```
POST /strategies/live-trading/{instance_id}/pause
POST /strategies/live-trading/{instance_id}/resume
POST /strategies/live-trading/{instance_id}/stop
```

**停止请求体：**

```json
{
  "close_positions": false,
  "reason": "手动停止"
}
```

### 6.5 获取实盘信号订单

```
GET /strategies/live-trading/orders?instance_id=uuid&status=pending&limit=50&offset=0
```

| 参数 | 类型 | 说明 |
|------|------|------|
| instance_id | uuid | 按实例过滤 |
| status | string | 状态过滤：pending / confirmed / executed / rejected / expired |
| limit | int | 默认 50 |
| offset | int | 默认 0 |

### 6.6 确认信号订单

```
POST /strategies/live-trading/orders/{order_id}/confirm
```

> 确认后执行风控校验（8 阈值），通过则调用交易所下单。
> 60s 未确认自动过期。

**返回结果（成功）：**

```json
{
  "code": 0,
  "data": {
    "order_id": "uuid",
    "status": "executed",
    "exchange_order_id": "EX123456",
    "executed_price": 42000.5,
    "executed_amount": 0.235
  }
}
```

**返回结果（风控拦截）：**

```json
{
  "code": 400,
  "message": "风控拦截: 单日亏损 6.5% 超过上限 5.0%",
  "detail": { "code": 45001, "reason": "..." }
}
```

### 6.7 拒绝信号订单

```
POST /strategies/live-trading/orders/{order_id}/reject
```

**请求体（可选）：**

```json
{
  "reason": "不看好当前价位"
}
```

---

## 7. SSE 实时推送

### 7.1 回测进度 SSE

```
GET /strategies/backtests/{backtest_id}/progress
```

**Content-Type：** `text/event-stream`

**事件格式：**

```
data: {"backtest_id":"uuid","stage":"running","progress":50,"message":"执行回测"}\n\n
data: {"backtest_id":"uuid","stage":"done","progress":100,"message":"回测完成"}\n\n
data: [DONE]\n\n
```

**stage 取值：** `connected` / `init` / `fetching` / `running` / `saving` / `done` / `error`

### 7.2 模拟交易实时更新 SSE

```
GET /strategies/paper-trading/{paper_account_id}/stream
```

**事件类型：**

- `tick`：行情快照

```json
{
  "type": "tick",
  "price": 42000.5,
  "current_equity": 10500.0,
  "position": 0.12,
  "available_cash": 5000.0,
  "unrealized_pnl": 240.0
}
```

- `trade`：虚拟成交

```json
{
  "type": "trade",
  "side": "buy",
  "price": 42000.5,
  "quantity": 0.12,
  "current_equity": 10500.0,
  "position": 0.12
}
```

### 7.3 实盘信号 SSE

```
GET /strategies/live-trading/{instance_id}/stream
```

**事件类型：**

- `signal`：新信号生成（需用户确认）

```json
{
  "type": "signal",
  "order_id": "uuid",
  "side": "buy",
  "symbol": "BTC/USDT",
  "suggested_price": 42000.5,
  "suggested_amount": 0.0238,
  "reason": "double_ma 买入信号",
  "expires_at": "2026-08-14T10:01:00Z"
}
```

---

## 8. 风控八阈值

实盘下单前执行 8 项风控校验（对齐 PRD §9.2），任一不通过即拦截：

| # | 阈值 | 默认值 | 参数键 |
|---|------|--------|--------|
| 1 | 单次下单金额 | < 50,000 USDT | `max_single_order_value` |
| 2 | 单日下单数 | < 100 | `max_daily_orders` |
| 3 | 同币种持仓数 | < 2 | `max_holdings_per_symbol` |
| 4 | 总持仓数 | < 10 | `max_total_holdings` |
| 5 | 单日亏损 | < 5% | `max_daily_loss_pct` |
| 6 | 连续亏损次数 | < 5 | `max_consecutive_losses` |
| 7 | 策略最大回撤 | < 20% | `max_drawdown_pct` |
| 8 | 单笔预计亏损 | < 2% | `max_single_loss_pct` |

启动实盘实例时可通过 `risk_params` 覆盖默认值：

```json
{
  "risk_params": {
    "max_single_order_value": 20000,
    "max_daily_loss_pct": 0.03
  }
}
```

---

## 9. 策略 DSL 结构

策略规则使用结构化 DSL 定义，支持 3 层 AND/OR 条件嵌套：

```json
{
  "entry": {
    "condition_group": {
      "logic": "AND",
      "conditions": [
        {
          "type": "ma_cross",
          "params": { "fast": 5, "slow": 20, "direction": "golden" }
        }
      ],
      "groups": [
        {
          "logic": "OR",
          "conditions": [ /* 嵌套条件 */ ],
          "groups": [ /* 最多 3 层 */ ]
        }
      ]
    }
  },
  "exit": {
    "stop_loss": { "type": "pct", "value": 0.05 },
    "take_profit": { "type": "pct", "value": 0.10 },
    "time_stop": { "enabled": true, "bars": 100 }
  },
  "sizing": {
    "method": "fixed_pct",
    "value": 0.10,
    "max_positions": 3
  },
  "risk_control": {
    "max_drawdown_pct": 0.20,
    "max_single_loss_pct": 0.02
  }
}
```

### 内置模板策略

| 模板 | ID | 类别 | 说明 |
|------|-----|------|------|
| 双均线金叉死叉 | `tpl-double-ma-0001` | trend | 快慢均线交叉趋势追踪 |
| RSI 超买超卖反转 | `tpl-rsi-reversal-002` | mean_reversion | RSI 超卖买入、超买卖出 |
| 海龟突破 | `tpl-turtle-break-003` | breakout | 唐奇安通道突破 + ATR 止损 |

---

## 异步任务调度

| 任务 | Celery Beat | 说明 |
|------|------------|------|
| `run_backtest` | 按需触发 | 回测执行（K 线拉取 + 引擎计算 + 结果落库） |
| `paper_trading_tick` | 每 2 分钟 | 模拟交易信号生成 + 虚拟成交 + Redis 推送 |
| `live_signal_tick` | 每 2 分钟 | 实盘信号生成 → 创建 LiveOrder(pending) |
