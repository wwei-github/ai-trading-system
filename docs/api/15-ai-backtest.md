# 15-AI 回测接口文档

> 模块：AI 驱动策略回测
> 对齐方案：`docs/backend/07-AI回测增强与终止后端技术方案.md`、`docs/backend/08-AI回测K线分析优化后端技术方案.md`
> Base URL：`/api/v1/strategies/ai-backtest`

---

## 目录

1. [创建并启动 AI 回测](#1-创建并启动-ai-回测)
2. [获取 AI 回测历史列表](#2-获取-ai-回测历史列表)
3. [获取回测详情](#3-获取回测详情)
4. [获取交易明细](#4-获取交易明细)
5. [SSE 进度推送](#5-sse-进度推送)
6. [取消回测](#6-取消回测)
7. [终止运行中回测](#7-终止运行中回测)
8. [回测结果 AI 分析](#8-回测结果-ai-分析)
9. [策略优化](#9-策略优化)
10. [多策略融合优化](#10-多策略融合优化)
11. [Prompt 模板管理](#11-prompt-模板管理)
12. [数据模型](#12-数据模型)

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
  "use_ai": true,
  "use_local_model": false,
  "local_model_klines": 10
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
| use_local_model | bool | 否 | false | 是否启用本地模型预筛（Ollama） |
| local_model_klines | int | 否 | 10 | 本地模型预筛 K 线数量，5~50 |

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
    "use_local_model": false,
    "local_model_klines": 10,
    "status": "pending",
    "total_klines": 500,
    "completed_klines": 0,
    "progress": 0.0,
    "started_at": null,
    "completed_at": null,
    "result_summary": null,
    "parent_backtest_id": null,
    "strategy_ids": null,
    "ai_call_count": 0,
    "precheck_total": 0,
    "precheck_triggered": 0,
    "initial_analysis": null,
    "ai_analysis_logs": null,
    "prompt_template_ids": null,
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
| 400 | 40000 | AI 回测必须启用 AI 分析，请设置 use_ai=true | use_ai=false |
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
      },
      "ai_analysis": {
        "overall_assessment": "策略表现良好...",
        "strengths": ["趋势跟踪准确"],
        "weaknesses": ["震荡行情频繁开仓"],
        "market_adaptability": { "trend_market": "优秀", "range_market": "一般", "volatile_market": "较差" },
        "improvement_suggestions": ["建议增加震荡过滤器"],
        "score": 72
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
| ai_analysis | object | AI 分析结果（可选） |
| precheck_total | int | 预筛总次数 |
| precheck_triggered | int | 预筛触发深度分析次数 |
| precheck_trigger_rate | float | 预筛触发率（%） |
| use_local_model | bool | 是否启用本地模型预筛 |
| initial_trend | string | 初始化分析趋势 bullish/bearish/neutral |

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
        "ai_window_start": 250,
        "ai_window_end": 349,
        "trigger_reason": "ai_precheck",
        "created_at": "2026-08-14T10:51:00Z"
      }
    ]
  }
}
```

**新增字段说明（08-AI回测K线分析优化）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| ai_window_start | int | AI 分析窗口起始 K 线索引 |
| ai_window_end | int | AI 分析窗口结束 K 线索引 |
| trigger_reason | string | 触发 AI 分析的原因：local_model / ai_precheck / key_level_hit / deep_analysis |

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

data: {"backtest_id":"UUID","stage":"running","progress":50,"current_kline":250,"total_klines":500,"current_trades":5,"current_position":{"direction":"long","entry_price":61200.50,"quantity":0.049,"unrealized_pnl":45.20},"ai_analysis":{"trend":"bullish","strength":4,"summary":"多头趋势明确","decision":"hold","confidence":4,"reason":"均线多头排列"},"indicators":{"ma5":61500,"ma10":61000,"rsi_14":62},"message":"正在推进第 250/500 根 K 线"}

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
| cancelled | 用户终止 | - |

**SSE payload 新增字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| ai_analysis | object | 当前 K 线的 AI 分析结果（可选） |
| ai_analysis.trend | string | 市场趋势：bullish/bearish/neutral |
| ai_analysis.strength | int | 趋势强度 1-5 |
| ai_analysis.summary | string | 分析摘要 |
| ai_analysis.decision | string | 决策：open_long/open_short/close_long/close_short/hold |
| ai_analysis.confidence | int | 置信度 1-5 |
| ai_analysis.reason | string | 决策理由 |
| indicators | object | 当前技术指标（可选） |
| indicators.ma5 | float | MA5 |
| indicators.ma10 | float | MA10 |
| indicators.rsi_14 | float | RSI14 |
| precheck_total | int | 预筛总次数（08优化） |
| precheck_triggered | int | 预筛触发深度分析次数（08优化） |
| ai_call_count | int | AI 深度分析调用次数（08优化） |
| current_stage_detail | string | 当前阶段详情：suspended / holding / precheck / rule（08优化） |
| initial_analysis | object | 初始化分析结果（趋势+关键位）（08优化，已完成回测时） |
| ai_analysis_logs | array | 深度分析日志列表（08优化，已完成回测时） |

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

## 7. 终止运行中回测

```
POST /strategies/ai-backtest/{backtest_id}/stop
```

终止正在运行的 AI 回测。

**鉴权：** Trader+

**路径参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| backtest_id | UUID | 回测记录 ID |

**处理流程：**
1. 验证所有权 + 状态为 running
2. 设置 Redis 停止标志 (TTL 3600s)
3. 更新 DB 状态为 cancelling
4. 返回 {status: "stopping"}

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "status": "stopping"
  }
}
```

**注意：**
- 终止后，Celery Worker 会在下一根 K 线推进前检测到停止信号
- 已完成的交易会保留，未完成的交易丢弃
- 回测状态标记为 `cancelled`
- 通过 SSE 推送 `stage: "cancelled"` 事件

---

## 8. 回测结果 AI 分析

```
POST /strategies/ai-backtest/{backtest_id}/analyze
```

对已完成的回测进行 AI 分析。

**鉴权：** Trader+

**路径参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| backtest_id | UUID | 回测记录 ID |

**处理流程：**
1. 验证所有权 + 状态为 completed
2. 读取回测结果摘要 + 所有交易明细 + 策略规则
3. 调用 LLM 进行分析
4. 保存分析结果到 backtest.result_summary.ai_analysis
5. 返回分析结果

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "overall_assessment": "策略表现良好，胜率65%，但最大回撤偏高...",
    "strengths": ["趋势跟踪准确", "止损设置合理"],
    "weaknesses": ["震荡行情中频繁开仓", "止盈设置偏保守"],
    "market_adaptability": {
      "trend_market": "优秀",
      "range_market": "一般",
      "volatile_market": "较差"
    },
    "improvement_suggestions": [
      "建议增加震荡行情过滤器",
      "建议上调止盈目标至 1:2 盈亏比",
      "建议在 RSI<30 时加仓"
    ],
    "score": 72
  }
}
```

---

## 9. 策略优化

```
POST /strategies/ai-backtest/{backtest_id}/optimize
```

基于回测结果生成新的优化策略。

**鉴权：** Trader+

**路径参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| backtest_id | UUID | 回测记录 ID |

**前置条件：** 必须先调用 AI 分析（`/analyze`）成功

**处理流程：**
1. 验证所有权 + 状态为 completed
2. 读取回测结果 + 已有 AI 分析 + 原策略规则
3. 调用 LLM 生成优化后的策略规则
4. 创建新策略记录（名称: "原策略名 - 优化版 vN"）
5. 在新策略 extra 记录 source_backtest_id
6. 返回新策略详情

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "id": "UUID",
    "name": "移动均线策略 - 优化版 v1",
    "rules": {
      "category": "technical",
      "entry_rules": [
        { "condition": "MA5 > MA10 且 RSI < 70", "params": {} }
      ],
      "exit_rules": [
        { "condition": "MA5 < MA10 或止损", "params": {} }
      ],
      "position_sizing": { "method": "fixed_percent", "base_percent": 30 },
      "risk_control": { "max_drawdown_pct": 15, "max_position_risk_pct": 2 },
      "prerequisites": {
        "single_position": { "enabled": true, "description": "单仓规则" },
        "mandatory_stop_loss": { "enabled": true, "default_stop_loss_pct": 3 },
        "strict_execution": { "enabled": true, "description": "严格执规" }
      },
      "optimization_notes": "优化说明"
    }
  }
}
```

---

## 10. 多策略融合优化

```
POST /strategies/ai-backtest/{backtest_id}/merge-optimize
```

基于多个策略的回测结果，通过 LLM 分析融合生成新策略，并自动创建子回测。

**鉴权：** Trader+

**路径参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| backtest_id | UUID | 父回测记录 ID |

**请求体：**

```json
{
  "strategy_ids": ["UUID1", "UUID2", "UUID3"],
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "name": "融合策略名称"
}
```

**参数说明：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| strategy_ids | string[] | 是 | - | 参与融合的策略 ID 列表，至少 2 个 |
| symbol | string | 是 | - | 交易对 |
| timeframe | string | 是 | - | 时间周期 |
| name | string | 否 | 自动生成 | 融合策略名称 |

**处理流程：**
1. 验证所有策略存在且属于当前用户
2. 验证父回测状态为 completed
3. 调用 LLM 分析各策略表现，生成融合后的新策略规则
4. 创建新策略记录（关联 source_backtest_id）
5. 创建子回测并自动启动（关联 parent_backtest_id）
6. 返回子回测详情

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "id": "UUID",
    "strategy_id": "UUID",
    "strategy_name": "融合策略名称",
    "parent_backtest_id": "UUID",
    "strategy_ids": ["UUID1", "UUID2", "UUID3"],
    "status": "pending",
    "symbol": "BTC/USDT",
    "timeframe": "15m",
    "total_klines": 500,
    "completed_klines": 0,
    "progress": 0.0,
    "created_at": "2026-08-15T03:00:00Z"
  }
}
```

---

## 11. Prompt 模板管理

```
Base URL：/api/v1/ai/prompt-templates
```

管理 AI 回测各阶段使用的 Prompt 模板，支持按分类管理。

**分类说明：**

| 分类 | 说明 |
|---|---|
| initial_analysis | 初始化 300 根 K 线分析模板 |
| backtest_precheck | 快速预筛模板（两级 AI 过滤第一级） |
| deep_analysis | 深度分析模板（两级 AI 过滤第二级） |

### 11.1 获取模板列表

```
GET /api/v1/ai/prompt-templates
```

**查询参数：**

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| category | string | 全部 | 可选：initial_analysis / backtest_precheck / deep_analysis |
| active_only | bool | false | 仅返回启用的模板 |

**返回结果：**

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "UUID",
        "category": "initial_analysis",
        "name": "初始化分析模板 v1",
        "is_active": true,
        "version": 1,
        "created_at": "2026-08-15T03:00:00Z",
        "updated_at": null
      }
    ],
    "total": 1
  }
}
```

### 11.2 获取模板详情

```
GET /api/v1/ai/prompt-templates/{template_id}
```

### 11.3 创建模板

```
POST /api/v1/ai/prompt-templates
```

**请求体：**

```json
{
  "category": "initial_analysis",
  "name": "初始化分析模板 v1",
  "content": "你是一个专业的加密货币市场分析师...",
  "is_active": true
}
```

**参数说明：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| category | string | 是 | - | initial_analysis / backtest_precheck / deep_analysis |
| name | string | 是 | - | 模板名称，最大 200 字符 |
| content | string | 是 | - | 模板内容，支持 {} 占位符 |
| is_active | bool | 否 | true | 是否启用 |

### 11.4 更新模板

```
PATCH /api/v1/ai/prompt-templates/{template_id}
```

**请求体：**

```json
{
  "name": "初始化分析模板 v2",
  "content": "更新后的模板内容...",
  "is_active": true
}
```

**注意：** 每次更新自动将版本号 `version + 1`

### 11.5 删除模板

```
DELETE /api/v1/ai/prompt-templates/{template_id}
```

---

## 12. 数据模型

### 12.1 AIBacktest（ai_backtests 表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| parent_backtest_id | UUID | 多策略融合父回测 ID（可选） |
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
| use_local_model | BOOLEAN | 是否启用本地模型预筛 |
| local_model_klines | INTEGER | 本地模型预筛 K 线数量 |
| total_klines | INTEGER | 总 K 线数 |
| completed_klines | INTEGER | 已推进 K 线数 |
| status | VARCHAR(20) | pending / running / completed / failed / cancelling / cancelled |
| result_summary | JSONB | 回测总结指标（含 ai_analysis、precheck 统计） |
| strategy_ids | JSONB | 多策略融合策略 ID 列表 |
| ai_call_count | INTEGER | AI 深度分析调用次数 |
| precheck_total | INTEGER | 预筛总次数 |
| precheck_triggered | INTEGER | 预筛触发深度分析次数 |
| initial_analysis | JSONB | 初始化 300 根 K 线分析结果（趋势+关键位） |
| ai_analysis_logs | JSONB | 深度分析日志列表 |
| prompt_template_ids | JSONB | Prompt 模板 ID 映射 |
| started_at | TIMESTAMPTZ | 开始执行时间 |
| completed_at | TIMESTAMPTZ | 完成时间 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

### 12.2 AIBacktestTrade（ai_backtest_trades 表）

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
| ai_window_start | INTEGER | AI 分析窗口起始索引（08优化） |
| ai_window_end | INTEGER | AI 分析窗口结束索引（08优化） |
| trigger_reason | VARCHAR(50) | 触发 AI 分析的原因（08优化） |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

### 12.3 PromptTemplate（prompt_templates 表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| category | VARCHAR(50) | 模板分类：initial_analysis / backtest_precheck / deep_analysis |
| name | VARCHAR(200) | 模板名称 |
| content | TEXT | 模板内容（支持 {} 占位符） |
| is_active | BOOLEAN | 是否启用 |
| version | INTEGER | 版本号，每次更新 +1 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |