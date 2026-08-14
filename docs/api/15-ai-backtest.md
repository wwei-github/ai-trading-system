# 15-AI 回测接口文档

> 模块：AI 驱动策略回测
> 对齐方案：`docs/backend/06-AI驱动策略回测模式后端技术方案.md`
> Base URL：`/api/v1/strategies/ai-backtest`

---

## 目录

1. [创建并启动 AI 回测](#1-创建并启动-ai-回测)
2. [获取 AI 回测历史列表](#2-获取-ai-回测历史列表)
3. [获取回测详情](#3-获取回测详情)
4. [获取交易明细](#4-获取交易明细)
5. [SSE 进度推送](#5-sse-进度推送)
6. [取消回测](#6-取消回测)
7. [数据模型](#7-数据模型)

---

## 1. 创建并启动 AI 回测

```
POST /strategies/ai-backtest
```

创建 AI 回测记录并异步提交 Celery 任务执行回测。

**鉴权：** Trader+

**请求体：**

```json
{
  "strategy_id": "UUID",
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "start_time": "2026-08-01T00:00:00Z",
  "mode": "kline_count",
  "kline_count": 500,
  "initial_capital": 10000.00,
  "fee_rate": 0.001,
  "use_ai": true
}
```

**参数说明：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| strategy_id | UUID | 是 | - | 策略 ID（非 draft 状态，规则非空） |
| symbol | string | 是 | BTC/USDT | 交易对，最大 20 字符 |
| timeframe | string | 是 | 15m | 可选：15m / 1h / 4h / 1d |
| start_time | datetime | 是 | - | 回测起始时间 |
| mode | string | 是 | kline_count | 可选：kline_count / time_span |
| kline_count | int | 否 | null | mode=kline_count 时必填，1~5000 |
| time_span_value | int | 否 | null | mode=time_span 时必填，1~365 |
| time_span_unit | string | 否 | null | mode=time_span 时必填，hour / day |
| initial_capital | float | 否 | 10000.00 | 初始资金，100~100,000,000 |
| fee_rate | float | 否 | 0.001 | 手续费率，0~0.01 |
| use_ai | bool | 否 | true | 是否启用 AI 决策 |

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "id": "UUID",
    "strategy_id": "UUID",
    "strategy_name": "移动均线策略",
    "symbol": "BTC/USDT",
    "timeframe": "15m",
    "start_time": "2026-08-01T00:00:00Z",
    "end_time": null,
    "mode": "kline_count",
    "kline_count": 500,
    "time_span_value": null,
    "time_span_unit": null,
    "initial_capital": 10000.00,
    "fee_rate": 0.001,
    "use_ai": true,
    "status": "pending",
    "total_klines": 500,
    "completed_klines": 0,
    "progress": 0.0,
    "started_at": null,
    "completed_at": null,
    "result_summary": null,
    "created_at": "2026-08-14T10:49:00Z"
  }
}
```

**错误码：**

| HTTP 状态 | code | message | 触发场景 |
|---|---|---|---|
| 400 | 40000 | 同一用户最多同时运行 3 个 AI 回测 | 并发超限 |
| 400 | 40000 | 草稿状态的策略不可用于回测 | 策略状态校验 |
| 400 | 40000 | 策略规则为空 | 策略规则校验 |
| 400 | 40000 | 无法获取历史 K 线数据 | 数据源不可用 |
| 404 | 40400 | 策略不存在 | 策略 ID 不存在或不属于当前用户 |

---

## 2. 获取 AI 回测历史列表

```
GET /strategies/ai-backtest/list
```

**鉴权：** Trader+

**查询参数：**

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| page | int | 1 | 页码，≥1 |
| page_size | int | 10 | 每页条数，1~100 |

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "total": 5,
    "page": 1,
    "page_size": 10,
    "items": [
      {
        "id": "UUID",
        "strategy_name": "移动均线策略",
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "status": "completed",
        "total_klines": 500,
        "completed_klines": 500,
        "initial_capital": 10000.00,
        "total_pnl": 520.15,
        "win_rate": 65.5,
        "trade_count": 18,
        "created_at": "2026-08-14T10:49:00Z",
        "completed_at": "2026-08-14T10:51:00Z"
      }
    ]
  }
}
```

---

## 3. 获取回测详情

```
GET /strategies/ai-backtest/{backtest_id}
```

**鉴权：** Trader+

**路径参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| backtest_id | UUID | 回测记录 ID |

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "id": "UUID",
    "strategy_id": "UUID",
    "strategy_name": "移动均线策略",
    "symbol": "BTC/USDT",
    "timeframe": "15m",
    "start_time": "2026-08-01T00:00:00Z",
    "end_time": null,
    "mode": "kline_count",
    "kline_count": 500,
    "time_span_value": null,
    "time_span_unit": null,
    "initial_capital": 10000.00,
    "fee_rate": 0.001,
    "use_ai": true,
    "status": "completed",
    "total_klines": 500,
    "completed_klines": 500,
    "progress": 100.0,
    "started_at": "2026-08-14T10:49:30Z",
    "completed_at": "2026-08-14T10:51:00Z",
    "result_summary": {
      "total_trades": 18,
      "total_pnl": 520.15,
      "total_return_pct": 5.2,
      "win_rate": 65.5,
      "max_single_profit": 185.30,
      "max_single_loss": -92.45,
      "avg_pnl": 28.9,
      "max_consecutive_wins": 5,
      "max_consecutive_losses": 3,
      "max_drawdown_pct": 3.8,
      "final_equity": 10520.15,
      "total_fee": 12.35,
      "avg_holding_bars": 8.5,
      "ai_calls": 500,
      "open_count": 18,
      "close_reasons": {
        "AI 决策平仓": 12,
        "止损": 6
      }
    },
    "created_at": "2026-08-14T10:49:00Z"
  }
}
```

**result_summary 字段说明：**

| 字段 | 类型 | 说明 |
|---|---|---|
| total_trades | int | 总交易次数 |
| total_pnl | float | 总盈亏 |
| total_return_pct | float | 总收益率百分比 |
| win_rate | float | 胜率百分比 |
| max_single_profit | float | 单笔最大盈利 |
| max_single_loss | float | 单笔最大亏损 |
| avg_pnl | float | 平均每笔盈亏 |
| max_consecutive_wins | int | 最大连胜次数 |
| max_consecutive_losses | int | 最大连败次数 |
| max_drawdown_pct | float | 最大回撤百分比 |
| final_equity | float | 最终权益 |
| total_fee | float | 总手续费 |
| avg_holding_bars | float | 平均持仓 K 线数 |
| ai_calls | int | AI 调用次数 |
| open_count | int | 开仓次数 |
| close_reasons | object | 平仓原因分布 |

---

## 4. 获取交易明细

```
GET /strategies/ai-backtest/{backtest_id}/trades
```

**鉴权：** Trader+

**路径参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| backtest_id | UUID | 回测记录 ID |

**查询参数：**

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| page | int | 1 | 页码，≥1 |
| page_size | int | 20 | 每页条数，1~50 |

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "total": 18,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "id": "UUID",
        "index": 1,
        "direction": "long",
        "entry_time": "2026-08-01T03:00:00Z",
        "entry_price": 61200.5000,
        "quantity": 0.04901961,
        "open_ai_analysis": "{\"market_analysis\":{...}}",
        "open_reason": "均线多头排列，RSI 处于 50-70 强区间",
        "open_confidence": 4,
        "stop_loss": 59364.4850,
        "take_profit": 64260.5250,
        "exit_time": "2026-08-03T12:00:00Z",
        "exit_price": 63800.0000,
        "exit_reason": "AI 决策平仓",
        "exit_ai_analysis": "{\"market_analysis\":{...}}",
        "exit_confidence": null,
        "holding_bars": 8,
        "pnl": 127.45,
        "pnl_pct": 2.5,
        "fee": 0.15,
        "extra": null,
        "created_at": "2026-08-14T10:51:00Z"
      }
    ]
  }
}
```

---

## 5. SSE 进度推送

```
GET /strategies/ai-backtest/{backtest_id}/progress
```

SSE（Server-Sent Events）流式推送回测进度。

**鉴权：** Trader+

**返回格式：** `text/event-stream`

**事件数据：**

```
data: {"backtest_id":"UUID","stage":"preheat","progress":2,"current_kline":0,"total_klines":500,"current_trades":0,"current_position":null,"message":"正在获取预热数据..."}

data: {"backtest_id":"UUID","stage":"running","progress":50,"current_kline":250,"total_klines":500,"current_trades":5,"current_position":{"direction":"long","entry_price":61200.50,"quantity":0.049,"unrealized_pnl":45.20},"message":"正在推进第 250/500 根 K 线"}

data: {"backtest_id":"UUID","stage":"summary","progress":98,"current_kline":500,"total_klines":500,"current_trades":18,"current_position":null,"message":"正在生成总结报告..."}

data: {"backtest_id":"UUID","stage":"done","progress":100,"current_kline":500,"total_klines":500,"current_trades":18,"current_position":null,"message":"回测完成"}

data: [DONE]
```

**stage 说明：**

| stage | 说明 | 进度范围 |
|---|---|---|
| preheat | 预热阶段（获取300根历史K线） | 0~5 |
| running | 逐根推进阶段 | 5~95 |
| summary | 生成总结报告 | 95~98 |
| done | 回测完成 | 100 |
| error | 回测失败 | - |

**注意：**
- 若回测已完成或失败，SSE 直接返回最终状态并立即结束
- 超时时间：1 小时
- 回测期间每 10 根 K 线推送一次

---

## 6. 取消回测

```
POST /strategies/ai-backtest/{backtest_id}/cancel
```

取消待开始状态的 AI 回测（仅 pending 状态可取消）。

**鉴权：** Trader+

**路径参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| backtest_id | UUID | 回测记录 ID |

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "status": "cancelled"
  }
}
```

---

## 7. 数据模型

### 7.1 AIBacktest（ai_backtests 表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| strategy_id | UUID | 关联策略 ID |
| user_id | UUID | 用户 ID |
| symbol | VARCHAR(20) | 交易对 |
| timeframe | VARCHAR(10) | 时间周期 |
| start_time | TIMESTAMPTZ | 回测起始时间 |
| end_time | TIMESTAMPTZ | 回测结束时间（自动计算） |
| mode | VARCHAR(20) | kline_count / time_span |
| kline_count | INTEGER | mode=kline_count 时 K 线数量 |
| time_span_value | INTEGER | mode=time_span 时时间跨度值 |
| time_span_unit | VARCHAR(10) | mode=time_span 时时间跨度单位 |
| initial_capital | NUMERIC(20,2) | 初始资金 |
| fee_rate | FLOAT | 手续费率，默认 0.001 |
| use_ai | BOOLEAN | 是否启用 AI 决策，默认 true |
| total_klines | INTEGER | 总 K 线数 |
| completed_klines | INTEGER | 已推进 K 线数 |
| status | VARCHAR(20) | pending / running / completed / failed |
| result_summary | JSONB | 回测总结指标 |
| started_at | TIMESTAMPTZ | 开始执行时间 |
| completed_at | TIMESTAMPTZ | 完成时间 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

### 7.2 AIBacktestTrade（ai_backtest_trades 表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| backtest_id | UUID | 关联回测 ID |
| index | INTEGER | 交易序号 |
| direction | VARCHAR(10) | long / short |
| entry_time | TIMESTAMPTZ | 开仓时间 |
| entry_price | NUMERIC(20,4) | 开仓价格 |
| quantity | NUMERIC(20,8) | 数量 |
| open_ai_analysis | TEXT | AI 开仓分析原始 JSON |
| open_reason | TEXT | 开仓理由 |
| open_confidence | INTEGER | 开仓置信度 1-5 |
| stop_loss | NUMERIC(20,4) | 止损价 |
| take_profit | NUMERIC(20,4) | 止盈价 |
| exit_time | TIMESTAMPTZ | 平仓时间 |
| exit_price | NUMERIC(20,4) | 平仓价格 |
| exit_reason | TEXT | 平仓理由 |
| exit_ai_analysis | TEXT | AI 平仓分析原始 JSON |
| exit_confidence | INTEGER | 平仓置信度 1-5 |
| holding_bars | INTEGER | 持仓 K 线数 |
| pnl | NUMERIC(20,2) | 盈亏 |
| pnl_pct | NUMERIC(10,4) | 盈亏百分比 |
| fee | NUMERIC(20,4) | 手续费 |
| extra | JSONB | 扩展字段 |
| created_at | TIMESTAMPTZ | 创建时间 |