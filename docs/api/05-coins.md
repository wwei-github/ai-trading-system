# 币种分析接口

> **模块前缀**: `/coins` ｜ **RBAC**: 登录可见（所有端点需登录）
> **数据源**: Binance 现货公开行情（无需 API Key）；K 线 DB 优先 + CCXT 补齐
> **缓存**: Redis（Top100 行情 30s；Ticker 15s；Redis 不可用时自动降级直查）

所有端点需 `Authorization: Bearer <access_token>`。

---

## 1. 端点清单

| # | 方法 | 路径 | 功能 |
|---|---|---|---|
| 1 | GET | `/coins/health` | 模块健康检查 |
| 2 | GET | `/coins` | Top100 行情列表（搜索 + 排序 + Redis 30s 缓存） |
| 3 | GET | `/coins/watchlist` | 用户自选列表（含实时行情 + 自添加以来涨跌幅） |
| 4 | POST | `/coins/watchlist` | 添加自选（每用户最多 200） |
| 5 | PATCH | `/coins/watchlist/{symbol}` | 更新自选（note / sort_order） |
| 6 | DELETE | `/coins/watchlist/{symbol}` | 移除自选 |
| 7 | GET | `/coins/compare` | 多币种对比（归一化收益 + 相关性矩阵） |
| 8 | GET | `/coins/{symbol}` | [兼容] 币种基本信息 |
| 9 | GET | `/coins/{symbol}/ticker` | 实时行情（Redis 15s 缓存） |
| 10 | GET | `/coins/{symbol}/kline` | K 线数据（DB 优先 + CCXT 补齐） |
| 11 | GET | `/coins/{symbol}/indicators` | 14 类技术指标 |
| 12 | GET | `/coins/{symbol}/analysis` | AI 分析报告（6 部分结构，V1 纯规则） |

> **路径符号约定**：URL 路径中 `/` 会被自动解码导致路由失败，前端可使用 `BTC-USDT` 或 `BTCUSDT`，后端 `_normalize_symbol` 自动转换为 CCXT 风格 `BTC/USDT`。

---

## 2. 数据模型

### 2.1 CoinInfo（币种基本信息）

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对（CCXT 风格，如 `BTC/USDT`） |
| `name` | string \| null | 币种名称（取交易对前半部分，如 `BTC`） |
| `current_price` | Decimal \| null | 当前价格 |
| `price_change_24h` | float \| null | 24h 涨跌幅（百分比，如 `2.35` 表示 +2.35%） |
| `volume_24h` | Decimal \| null | 24h 成交额（quote volume，USDT 计价） |
| `high_24h` | Decimal \| null | 24h 最高价 |
| `low_24h` | Decimal \| null | 24h 最低价 |
| `exchange` | string \| null | 数据来源交易所（默认 `binance`） |

### 2.2 TickerInfo（实时行情）

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对 |
| `name` | string | 币种名称 |
| `current_price` | Decimal \| null | 当前价格 |
| `price_change_24h` | float \| null | 24h 涨跌幅 |
| `volume_24h` | Decimal \| null | 24h 成交额 |
| `timestamp` | int \| null | 行情时间戳（毫秒） |

### 2.3 KlineItem（K 线单根）

| 字段 | 类型 | 说明 |
|---|---|---|
| `timestamp` | int | 开盘时间戳（毫秒） |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `volume` | float | 成交量 |

### 2.4 KlineResponse（K 线响应）

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对 |
| `timeframe` | string | 时间周期 |
| `data` | KlineItem[] | K 线数组（时间正序） |
| `source` | string | 数据来源：`ccxt` / `db` / `ccxt+db` |
| `last_updated` | datetime \| null | 最后更新时间（UTC） |

### 2.5 IndicatorResponse（技术指标响应）

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对 |
| `timeframe` | string | 时间周期 |
| `indicators` | Dict | 指标结果，key 为指标类型，value 为该指标的多个键值 |
| `calculated_at` | datetime | 计算时间（UTC） |

### 2.6 CompareResponse（多币种对比响应）

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbols` | string[] | 实际参与对比的币种列表 |
| `days` | int | 实际对比天数 |
| `normalized_curve` | ComparePoint[] | 归一化收益曲线（首日 0%，后续累计） |
| `correlation` | CorrelationMatrix \| null | N×N 相关性矩阵 |
| `summary` | Dict | 每币种汇总：`return_pct`/`volatility_pct`/`sharpe` |

### 2.7 AnalysisReport（AI 分析报告，6 部分）

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对 |
| `timeframe` | string | 时间周期 |
| `generated_at` | datetime | 生成时间（UTC） |
| `trend` | AnalysisTrend \| null | 1. 趋势判断 |
| `support_resistance` | SupportResistance \| null | 2. 支撑阻力 |
| `indicator_signals` | IndicatorSignals \| null | 3. 指标信号汇总 |
| `volume_price` | VolumePriceFeature \| null | 4. 量价特征 |
| `risk` | RiskAssessment \| null | 5. 风险评估 |
| `recommendation` | AnalysisRecommendation \| null | 6. 操作建议 |

### 2.8 WatchlistItem（用户自选项）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 自选项 ID（UUID） |
| `user_id` | string | 用户 ID |
| `symbol` | string | 交易对 |
| `note` | string \| null | 备注（≤200 字） |
| `sort_order` | int | 排序值（默认 100） |
| `added_price` | float \| null | 添加时价格 |
| `created_at` | datetime | 添加时间 |
| `current_price` | Decimal \| null | 当前价格（实时填充） |
| `price_change_24h` | float \| null | 24h 涨跌幅（实时填充） |
| `price_change_since_added` | float \| null | 自添加以来涨跌幅（%） |

---

## 3. 接口详情

### 3.1 GET `/coins/health` — 模块健康检查

**说明**：币种分析模块健康检查。

**请求参数**：无

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "ok",
    "module": "coins"
  }
}
```

---

### 3.2 GET `/coins` — Top100 行情列表

**说明**：获取 Top100 币种行情（Binance 现货 /USDT 交易对，按 24h 成交额排序，Redis 30s 缓存）。

**查询参数**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `limit` | int | — | 100 | 返回数量（1-200） |
| `search` | string | — | — | 按名称/代码搜索（如 `BTC`） |
| `sort_by` | string | — | `volume_24h` | 排序字段：`volume_24h` / `price_change_24h` / `current_price` |
| `sort_order` | string | — | `desc` | `asc` / `desc` |

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "symbol": "BTC/USDT",
      "name": "BTC",
      "current_price": "43250.50",
      "price_change_24h": 2.35,
      "volume_24h": "12345678900.00",
      "high_24h": "44000.00",
      "low_24h": "42100.00",
      "exchange": "binance"
    }
  ]
}
```

**错误**：

| code | HTTP | 场景 |
|---|---|---|
| 503 | 503 | 交易所连接失败（`ServiceUnavailableException`） |

---

### 3.3 GET `/coins/watchlist` — 用户自选列表

**说明**：获取当前用户自选币种列表，自动填充实时行情与自添加以来涨跌幅。

**请求参数**：无

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "user-uuid",
      "symbol": "BTC/USDT",
      "note": "长期持有",
      "sort_order": 100,
      "added_price": 38000.0,
      "created_at": "2026-08-01T10:00:00Z",
      "current_price": "43250.50",
      "price_change_24h": 2.35,
      "price_change_since_added": 13.82
    }
  ]
}
```

---

### 3.4 POST `/coins/watchlist` — 添加自选

**说明**：添加币种到自选列表。每用户最多 200 个（PRD §5.5.1 R3）。添加时自动记录当时价格用于后续涨跌幅计算。

**请求体（JSON）**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `symbol` | string | ✅ | 交易对，如 `BTC/USDT` |
| `note` | string | — | 备注（≤200 字） |
| `sort_order` | int | — | 排序值（0-10000，默认 100） |

**请求示例**：

```json
{
  "symbol": "ETH/USDT",
  "note": "中长线观察",
  "sort_order": 50
}
```

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "new-uuid",
    "user_id": "user-uuid",
    "symbol": "ETH/USDT",
    "note": "中长线观察",
    "sort_order": 50,
    "added_price": 2280.5,
    "created_at": "2026-08-14T08:30:00Z",
    "current_price": "2280.50"
  }
}
```

**错误**：

| code | HTTP | 场景 |
|---|---|---|
| 400 | 400 | 自选已达上限（200）/ 重复添加（`BadRequestException`） |
| 503 | 503 | 数据库不可用 |

---

### 3.5 PATCH `/coins/watchlist/{symbol}` — 更新自选

**说明**：更新自选项的备注或排序。`symbol` 路径参数支持 `BTC-USDT` / `BTCUSDT` / `BTC/USDT` 三种格式（自动规范化）。

**路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对（自动规范化为 CCXT 风格） |

**请求体（JSON）**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `note` | string | — | 新备注（≤200 字） |
| `sort_order` | int | — | 新排序值（0-10000） |

**请求示例**：

```json
{
  "note": "调整为止损位 42000",
  "sort_order": 10
}
```

**响应示例**：返回更新后的 WatchlistItem（同 3.3）。

**错误**：

| code | HTTP | 场景 |
|---|---|---|
| 404 | 404 | 自选项不存在 |

---

### 3.6 DELETE `/coins/watchlist/{symbol}` — 移除自选

**说明**：从自选列表移除指定币种。

**路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对（自动规范化） |

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "removed": true,
    "symbol": "BTC/USDT"
  }
}
```

---

### 3.7 GET `/coins/compare` — 多币种对比

**说明**：对比 2-8 个币种，返回归一化收益曲线（首日 0%）+ N×N 相关性矩阵（Pearson 系数）+ 每币种收益/波动率/夏普汇总。

**查询参数**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `symbols` | string | ✅ | — | 交易对列表，逗号分隔，如 `BTC/USDT,ETH/USDT`（2-8 个） |
| `timeframe` | string | — | `1d` | K 线周期 |
| `days` | int | — | 30 | 对比天数（7-365） |

**请求示例**：

```
GET /coins/compare?symbols=BTC/USDT,ETH/USDT,SOL/USDT&days=30
```

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    "days": 30,
    "normalized_curve": [
      { "date": "2026-07-15", "values": { "BTC/USDT": 0.0, "ETH/USDT": 0.0, "SOL/USDT": 0.0 } },
      { "date": "2026-07-16", "values": { "BTC/USDT": 0.012, "ETH/USDT": 0.018, "SOL/USDT": -0.005 } }
    ],
    "correlation": {
      "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
      "matrix": [
        [1.0, 0.85, 0.72],
        [0.85, 1.0, 0.68],
        [0.72, 0.68, 1.0]
      ]
    },
    "summary": {
      "BTC/USDT": { "return_pct": 5.23, "volatility_pct": 45.2, "sharpe": 0.12 },
      "ETH/USDT": { "return_pct": 8.15, "volatility_pct": 52.8, "sharpe": 0.15 },
      "SOL/USDT": { "return_pct": -3.42, "volatility_pct": 78.5, "sharpe": -0.04 }
    }
  }
}
```

**错误**：

| code | HTTP | 场景 |
|---|---|---|
| 400 | 400 | 币种数量 < 2 或 > 8 |
| 503 | 503 | K 线数据不足（少于 2 个币种有数据） |

---

### 3.8 GET `/coins/{symbol}` — [兼容] 币种基本信息

**说明**：获取币种基本信息（含实时行情）。等同于 ticker 的精简版。

**路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对（自动规范化） |

**响应示例**：返回 [CoinInfo](#21-coininfo币种基本信息) 结构。

---

### 3.9 GET `/coins/{symbol}/ticker` — 实时行情

**说明**：获取币种实时行情，Redis 15s 缓存。

**路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对（自动规范化） |

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "symbol": "BTC/USDT",
    "name": "BTC",
    "current_price": "43250.50",
    "price_change_24h": 2.35,
    "volume_24h": "12345678900.00",
    "timestamp": 1723520400000
  }
}
```

**错误**：

| code | HTTP | 场景 |
|---|---|---|
| 503 | 503 | 交易所连接失败 |

---

### 3.10 GET `/coins/{symbol}/kline` — K 线数据

**说明**：获取 K 线数据（OHLCV）。

**策略**：
1. 优先读 DB（`klines` 表，按 `open_time` 降序取 `limit` 根）
2. 若数量不足或最新一根已过期（超过 2 个周期），从 CCXT 补齐并入库（唯一索引 `(symbol, timeframe, open_time)` 自动去重）
3. 返回数据按时间正序排列（前端 K 线图需要）

**路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对（自动规范化） |

**查询参数**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `timeframe` | string | — | `1d` | 时间周期：`1m`/`5m`/`15m`/`30m`/`1h`/`2h`/`4h`/`6h`/`12h`/`1d`/`3d`/`1w`/`1M` |
| `limit` | int | — | 200 | K 线数量（1-1000） |

**请求示例**：

```
GET /coins/BTC-USDT/kline?timeframe=1h&limit=500
```

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "symbol": "BTC/USDT",
    "timeframe": "1d",
    "data": [
      { "timestamp": 1723520400000, "open": 42100.0, "high": 44000.0, "low": 42000.0, "close": 43250.5, "volume": 12345.67 },
      { "timestamp": 1723606800000, "open": 43250.5, "high": 44500.0, "low": 43000.0, "close": 44100.0, "volume": 9876.54 }
    ],
    "source": "ccxt+db",
    "last_updated": "2026-08-14T08:30:00Z"
  }
}
```

**错误**：

| code | HTTP | 场景 |
|---|---|---|
| 503 | 503 | DB 无数据且 CCXT 拉取失败 |

---

### 3.11 GET `/coins/{symbol}/indicators` — 14 类技术指标

**说明**：基于 K 线数据计算 14 类技术指标（PRD §5.5.2），返回各指标最新值。算法对齐 TradingView 默认参数，误差 ≤ 0.1%。

**指标清单**：

| 类别 | 指标 | key | 默认参数 | 返回字段 |
|---|---|---|---|---|
| 均线 | MA | `ma` | periods=[5,10,20,60,120,200] | `ma5`/`ma10`/`ma20`/`ma60`/`ma120`/`ma200` |
| 均线 | EMA | `ema` | periods=[5,10,20,60] | `ema5`/`ema10`/`ema20`/`ema60` |
| 趋势 | MACD | `macd` | fast=12, slow=26, signal=9 | `macd`/`macd_signal`/`macd_hist` |
| 趋势 | BOLL | `boll` | period=20, std=2 | `boll_upper`/`boll_middle`/`boll_lower` |
| 趋势 | DMI | `dmi` | period=14 | `pdi`/`mdi`/`adx`/`adxr` |
| 震荡 | RSI | `rsi` | period=14 | `rsi` |
| 震荡 | KDJ | `kdj` | period=9 | `k`/`d`/`j` |
| 震荡 | CCI | `cci` | period=20 | `cci` |
| 震荡 | Williams %R | `willr` | period=14 | `willr` |
| 成交量 | OBV | `obv` | — | `obv` |
| 成交量 | VWAP | `vwap` | — | `vwap` |
| 波动 | ATR | `atr` | period=14 | `atr` |
| 波动 | 标准差通道 | `stdch` | period=20, std=2 | `stdch_upper`/`stdch_middle`/`stdch_lower` |

> 注：14 类对应 13 个 `key`（MA 含 6 个周期），共 13 个计算函数，注册在 `INDICATOR_REGISTRY`。

**路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对（自动规范化） |

**查询参数**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `timeframe` | string | — | `1d` | 时间周期 |
| `types` | string | — | 全部 | 指标类型，逗号分隔；如 `ma,rsi,macd,boll,atr` |
| `limit` | int | — | 200 | K 线数量（≥50，用于计算指标） |

**请求示例**：

```
GET /coins/BTC-USDT/indicators?types=ma,rsi,macd,boll,atr&limit=200
```

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "symbol": "BTC/USDT",
    "timeframe": "1d",
    "indicators": {
      "ma": {
        "ma5": 43100.50,
        "ma10": 42850.20,
        "ma20": 42100.80,
        "ma60": 40500.30,
        "ma120": 38200.50,
        "ma200": 35100.20
      },
      "rsi": { "rsi": 62.35 },
      "macd": {
        "macd": 125.40,
        "macd_signal": 98.20,
        "macd_hist": 27.20
      },
      "boll": {
        "boll_upper": 45200.00,
        "boll_middle": 42100.80,
        "boll_lower": 39001.60
      },
      "atr": { "atr": 850.50 }
    },
    "calculated_at": "2026-08-14T08:30:00Z"
  }
}
```

**说明**：数据不足时对应字段为 `null`；指标计算失败时该指标返回 `{"error": "<原因>"}`。

---

### 3.12 GET `/coins/{symbol}/analysis` — AI 分析报告

**说明**：生成 AI 分析报告（6 部分结构，V1 为纯规则实现，V1.3 将升级为 LLM 版本）。对齐 PRD §5.5.4。

**报告结构**：

| 部分 | 字段 | 说明 |
|---|---|---|
| 1. 趋势判断 | `trend` | 短/中/长期 MA 多空排列（MA5/MA20/MA60 vs 现价） |
| 2. 支撑阻力 | `support_resistance` | 近 60 根 K 线高低点 + Fibonacci 回撤 0.382/0.5/0.618 |
| 3. 指标信号 | `indicator_signals` | MA / RSI / MACD / BOLL 信号汇总 + 多空评分 |
| 4. 量价特征 | `volume_price` | 近 5 日 vs 20 日均量比 + 量价背离判断 |
| 5. 风险评估 | `risk` | 年化波动率 + z-score（相对 60 日历史）+ 流动性评分 |
| 6. 操作建议 | `recommendation` | 观察 / 轻仓尝试 / 不推荐 3 档（含免责声明） |

**路径参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 交易对（自动规范化） |

**查询参数**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `timeframe` | string | — | `1d` | 时间周期 |

**请求示例**：

```
GET /coins/BTC-USDT/analysis?timeframe=1d
```

**响应示例**：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "symbol": "BTC/USDT",
    "timeframe": "1d",
    "generated_at": "2026-08-14T08:30:00Z",
    "trend": {
      "short_term": "bullish",
      "mid_term": "bullish",
      "long_term": "bullish",
      "description": "短期 MA5 多头；中期 MA20 多头；长期 MA60 多头；整体多头排列，趋势向上"
    },
    "support_resistance": {
      "supports": [39001.60, 40500.30, 41250.95],
      "resistances": [43250.50, 43999.85, 45200.00],
      "fibonacci_levels": {
        "0.382": 41250.95,
        "0.5": 42100.80,
        "0.618": 42950.65
      }
    },
    "indicator_signals": {
      "ma_signal": "bullish",
      "rsi_signal": "neutral",
      "macd_signal": "bullish",
      "boll_signal": "neutral",
      "summary": "偏多（2多/0空信号）"
    },
    "volume_price": {
      "volume_trend": "increasing",
      "price_volume_divergence": false,
      "description": "近 5 日成交量/20 日均值 = 1.35，趋势increasing"
    },
    "risk": {
      "volatility": 45.23,
      "volatility_zscore": 0.85,
      "liquidity_score": 78.50,
      "description": "年化波动率 45.23%"
    },
    "recommendation": {
      "action": "轻仓尝试",
      "confidence": 0.80,
      "reason": "多空评分 +3，多头信号占优",
      "disclaimer": "本报告基于规则计算，非投资建议，据此交易风险自负"
    }
  }
}
```

**操作建议评分规则**：

| 信号 | 评分 |
|---|---|
| 短期 MA 多头 / 空头 | +1 / -1 |
| 中期 MA 多头 / 空头 | +1 / -1 |
| 长期 MA 多头 / 空头 | +1 / -1 |
| MA5 vs MA20 多头 / 空头 | +1 / -1 |
| MACD 多头 / 空头 | +1 / -1 |
| RSI 超买 / 超卖 | -1 / +1 |

| 评分 | 建议 |
|---|---|
| ≥ 2 | 轻仓尝试 |
| ≤ -2 | 不推荐 |
| 其他 | 观察 |
| 波动率 z-score > 2 或年化波动率 > 100% | 强制降级为「不推荐」 |

**错误**：

| code | HTTP | 场景 |
|---|---|---|
| 503 | 503 | K 线数据不足（< 30 根） |

---

## 4. 缓存策略

| 端点 | 缓存键 | TTL | 降级 |
|---|---|---|---|
| `GET /coins`（Top100） | `coins:v1:top:{limit}:{search}:{sort_by}:{sort_order}` | 30s | Redis 不可用直查 CCXT |
| `GET /coins/{symbol}/ticker` | `coins:v1:ticker:{symbol}` | 15s | Redis 不可用直查 CCXT |
| K 线 | DB 表 `klines` 持久化 | — | DB 无数据时 CCXT 补齐 |

---

## 5. 数据库表

### 5.1 `klines`（K 线历史）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `symbol` | String(30) | 交易对（索引） |
| `timeframe` | String(10) | 时间周期（索引） |
| `open_time` | DateTime(tz) | 开盘时间（索引） |
| `open`/`high`/`low`/`close` | Float | OHLC |
| `volume` | Float | 成交量（默认 0） |
| `quote_volume` | Float \| null | 计价货币成交额 |
| `source` | String(20) | 来源（默认 `ccxt`） |
| `exchange` | String(30) | 交易所（默认 `binance`） |
| `created_at`/`updated_at` | DateTime | 时间戳 |

**约束**：
- 唯一约束 `uq_klines_symbol_tf_opentime`：(symbol, timeframe, open_time)
- 复合索引 `ix_klines_symbol_tf_time`：(symbol, timeframe, open_time)

### 5.2 `watchlist`（用户自选）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `user_id` | UUID | 用户 ID（外键 `users.id`） |
| `symbol` | String(30) | 交易对 |
| `note` | String(200) \| null | 备注 |
| `sort_order` | Integer | 排序值（默认 100） |
| `added_price` | Float \| null | 添加时价格 |
| `created_at`/`updated_at` | DateTime | 时间戳 |

**约束**：
- 唯一约束 `uq_watchlist_user_symbol`：(user_id, symbol)
- 复合索引 `ix_watchlist_user_sort`：(user_id, sort_order)

---

## 6. 相关代码

| 文件 | 说明 |
|---|---|
| [backend/app/api/v1/coins.py](../../backend/app/api/v1/coins.py) | 12 个端点定义 |
| [backend/app/services/coin_service.py](../../backend/app/services/coin_service.py) | 业务逻辑（行情聚合 / K 线 / 指标 / 对比 / 分析 / Watchlist） |
| [backend/app/schemas/coin.py](../../backend/app/schemas/coin.py) | Pydantic Schema |
| [backend/app/models/coin.py](../../backend/app/models/coin.py) | Kline / Watchlist ORM 模型 |
| [backend/app/utils/indicators.py](../../backend/app/utils/indicators.py) | 14 类技术指标计算 |
| [backend/app/exchange/ccxt_client.py](../../backend/app/exchange/ccxt_client.py) | CCXT 异步客户端封装 |
| [backend/alembic/versions/c5d6e7f8a9b0_stage5_coins_klines_watchlist.py](../../backend/alembic/versions/c5d6e7f8a9b0_stage5_coins_klines_watchlist.py) | Stage 5 数据库迁移 |
