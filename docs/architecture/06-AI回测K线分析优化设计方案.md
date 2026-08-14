# AI 回测 K 线分析优化设计方案

## 1. 背景与目标

### 1.1 当前问题

当前 AI 回测存在以下性能与效率问题：

| 问题               | 描述                                                        | 影响                                                       |
| ------------------ | ----------------------------------------------------------- | ---------------------------------------------------------- |
| 每根 K 线都调用 AI | 回测区间内每根 K 线都调用 LLM 分析                          | 大量 Token 消耗 + 回测极慢（300 根 K 线需 300 次 AI 调用） |
| AI 分析窗口过大    | 当前向 AI 传入全部历史数据，信息过载                        | AI 分析不聚焦，难以捕捉近期模式                            |
| 持仓期间仍调用 AI  | 开单后每根 K 线仍调用 AI 分析，但决策受单仓规则限制已被忽略 | 完全浪费的 AI 调用                                         |
| 不支持多策略融合   | 每次只能选一个策略回测，无法通过 AI 综合分析多个策略        | 缺少策略组合优化能力                                       |

### 1.2 优化目标

1. **两级过滤机制**：先用规则引擎或本地模型快速预筛，满足条件后再用 AI 深度分析，AI 调用减少 90%+
2. **K 线上限**：AI 最多只看最近 300 根 K 线，避免信息过载
3. **持仓免分析**：开单后跳过 AI 分析，直到平仓
4. **平仓后恢复**：单子结束后自动恢复 AI 分析
5. **多策略融合**：支持选择多个策略，AI 综合分析后生成新策略

### 1.3 补充需求：本地模型辅助预筛

在两级过滤基础上增加**本地模型辅助**选项（可选配置）：

- **AI 粗略预筛**（默认）：使用主 AI Provider 分析少量 K 线，粗略判断是否满足策略入场条件，速度快
- **本地模型预筛**（可选启用）：使用本地 Ollama 模型分析少量 K 线，语义理解更灵活，可在策略入场条件层面做智能判断
- 两种模式互斥，用户可通过前端开关切换
- 预筛分析的 K 线数量可配置（默认 10 根，范围 5-50）

---

## 2. 总体架构

### 2.1 核心流程对比

**优化前**（每根 K 线都调用 AI）：

```
K线[1] → AI分析 → 决策 → K线[2] → AI分析 → 决策 → ... → K线[n] → AI分析 → 决策
```

**优化后**（两级过滤 + 持仓免分析）：

```

K线[i]:
  ├─ 有持仓? ─→ 跳过AI，检查止损止盈 → 平仓? → 清除持仓，恢复AI分析
  │
  └─ 无持仓? ─→ 第一级：AI粗略预筛（少量K线）
                    │
                    ├─ [默认模式] 主AI粗略分析(recent_klines)
                    │     ├─ 不满足条件 → 继续下一根
                    │     └─ 满足条件 → 第二级：AI深度分析(300根)
                    │
                    ├─ [本地模型模式] 本地模型粗略分析(recent_klines)
                    │     ├─ 模型判断不满足 → 继续下一根
                    │     └─ 模型判断满足 → 第二级：AI深度分析(300根)
                    │
                    └─ 两种模式互斥，通过 use_local_model 配置切换
                                        ├─ 开仓决策 → 记录持仓，暂停AI分析
                                        └─ 不开仓 → 继续下一根
```

### 2.2 模块职责

| 模块                        | 职责                                                                                                    | 变更类型 |
| --------------------------- | ------------------------------------------------------------------------------------------------------- | -------- |
| `AIBacktestContext`         | 新增 `ai_analysis_paused` 状态位、`precheck_total`/`precheck_triggered` 计数、`local_model_klines` 配置 | 修改     |
| `AIMarketAnalyzer`          | 新增 `quick_precheck()` AI粗略预筛方法；新增 `analyze_with_window()` AI深度分析方法                     | 修改     |
| 新增 `LocalModelPrechecker` | 封装本地模型预筛逻辑，调用 Ollama 分析少量 K 线                                                         | 新增     |
| `AIBacktestService`         | 新增 `merge_optimize()` 多策略融合优化方法                                                              | 修改     |
| 前端 `AIBacktestConfigForm` | 新增多策略选择器 + 本地模型辅助开关 + K 线数量配置                                                      | 修改     |
| 前端 `AIBacktestPanel`      | 新增融合优化操作入口                                                                                    | 修改     |

---

## 3. 详细设计

### 3.1 两级过滤机制

#### 第一级：AI 粗略预筛（少量K线）

提供两种 AI 预筛模式，用户在配置时二选一：

**模式 A：主 AI 粗略预筛（默认）**

在 `AIMarketAnalyzer` 中新增 `quick_precheck()` 方法，使用主 AI Provider 分析少量 K 线：

```python
async def quick_precheck(
    self,
    kline_window: List[Dict],   # 可配置数量（默认 10 根，范围 5-50）
    strategy_rules: Dict,       # 策略入场规则
    symbol: str,
    timeframe: str,
) -> bool:
    """AI 粗略预筛：使用主 AI Provider 分析少量 K 线，判断是否满足策略入场条件。

    构建 Prompt 给 AI，要求 AI 快速判断最近 K 线是否出现了策略入场信号。
    只做粗略判断，不需要详细分析。

    Returns:
        True = 可能满足条件，触发第二级 AI 深度分析
        False = 不满足，跳过（不再调用 AI）
    """
```

**模式 B：本地模型预筛（可选）**

新增 `LocalModelPrechecker` 类，调用本地 Ollama 模型分析少量 K 线：

```python
class LocalModelPrechecker:
    """本地模型预筛器：使用 Ollama 分析少量 K 线是否满足策略入场条件。"""

    async def precheck(
        self,
        kline_window: List[Dict],       # 可配置数量（默认 10 根，范围 5-50）
        strategy_rules: Dict[str, Any], # 策略入场规则
        symbol: str,
        timeframe: str,
    ) -> bool:
        """调用本地 Ollama 模型检查 K 线是否满足入场条件。

        Returns:
            True = 满足条件，触发 AI 深度分析
            False = 不满足，跳过
        """
```

两种模式的核心区别：

- **模式 A**：使用主 AI Provider（如 GPT-4/Claude 等云端模型），分析质量高但有一定成本
- **模式 B**：使用本地 Ollama 模型，零成本但分析能力相对较弱
- 用户根据实际场景选择，两种模式互斥

#### 第二级：AI 深度分析（300根）

在 `AIMarketAnalyzer` 中新增 `analyze_with_window()` 方法：

```python
async def analyze_with_window(
    self,
    symbol: str,
    timeframe: str,
    kline_window: List[Dict],  # 最多 300 根
    indicators: Dict,
    position: Optional[Dict],
    strategy_rules: Dict,
    account_status: Dict,
    current_kline_index: int,
    total_klines: int,
) -> Dict[str, Any]:
    """AI 深度分析（限制 K 线窗口最多 300 根）。

    Args:
        kline_window: K 线窗口数据，最多 300 根
    """
```

### 3.2 持仓免分析

在 `AIBacktestContext` 中新增状态位：

```python
class AIBacktestContext:
    # ... 现有字段 ...

    # 新增字段
    self.ai_analysis_paused: bool = False  # AI 分析是否暂停（有持仓时）
    self.last_analysis_kline_index: int = 0  # 上次 AI 分析时的 K 线索引
    self.precheck_fast_count: int = 0        # 快速预筛总次数
    self.precheck_trigger_count: int = 0     # 预筛触发 AI 分析次数
```

在 `_run_backtest_async` 主循环中的逻辑：

```python
for idx, kline in enumerate(backtest_klines):
    # ...

    # 持仓免分析
    if ctx.current_position is not None:
        # 跳过 AI 分析，只检查止损止盈
        executor.execute(kline, None, indicators)
        # 检查是否已平仓
        if ctx.current_position is None:
            # 平仓了，恢复 AI 分析
            ctx.ai_analysis_paused = False
        continue

    # 无持仓：两级过滤
    if ctx.use_ai_real:
        # 第一级：快速预筛
        recent_klines = ctx.all_klines[max(0, ctx.preheat_count + idx - 9):ctx.preheat_count + idx + 1]
        if not executor._quick_precheck(kline, recent_klines, indicators):
            # 预筛未通过，使用规则引擎决策
            ai_result = None
        else:
            # 第二级：AI 深度分析（最多 300 根）
            window_start = max(0, ctx.preheat_count + idx - 299)
            kline_window = ctx.all_klines[window_start:ctx.preheat_count + idx + 1]
            ai_result = await analyzer.analyze_with_window(
                symbol=ctx.symbol,
                timeframe=ctx.timeframe,
                kline_window=kline_window,
                # ...
            )
            ctx.ai_call_count += 1
    else:
        ai_result = None

    # 执行决策
    executor.execute(kline, ai_result, indicators)
```

### 3.3 多策略融合

#### 数据结构

```python
# AIBacktest 表新增字段
parent_backtest_id: Optional[uuid.UUID] = None  # 融合回测时，记录来源回测
strategy_ids: Optional[List[uuid.UUID]] = None  # 选择的多个策略 ID
```

#### 融合优化流程

```
用户选择 N 个策略 → 分别启动 N 个 AI 回测 → 全部完成后
→ 用户点击"融合优化"
→ 后端读取 N 个回测结果 + N 个策略规则
→ 构建 Prompt 给 AI
→ AI 输出融合后的新策略规则
→ 创建新策略（名称: "多策略融合版 v1"）
```

#### Prompt 设计

```python
def _build_merge_optimize_prompt(
    self, strategies: List[Strategy], backtests: List[AIBacktest], analysis: Dict[str, Any]
) -> str:
    """构建多策略融合优化 Prompt。"""
    # 列出每个策略的规则和回测结果
    # 要求 AI 综合分析，取长补短，生成融合策略
```

### 3.4 本地模型预筛配置

#### 3.4.1 配置项

```python
# 本地模型预筛相关配置
use_local_model: bool = False          # 是否使用本地模型预筛（默认关闭，使用规则引擎）
local_model_klines: int = 10           # 本地模型分析的 K 线数量（默认 10，范围 5-50）
LOCAL_MODEL_MIN_KLINES: int = 5        # 最小 K 线数
LOCAL_MODEL_MAX_KLINES: int = 50       # 最大 K 线数
```

#### 3.4.2 存储方式

```python
# AIBacktest 表新增字段
use_local_model: bool = Field(False, description="使用本地模型进行预筛")
local_model_klines: int = Field(10, description="本地模型分析的 K 线数量")
```

#### 3.4.3 本地模型 Prompt 设计

```python
LOCAL_MODEL_PRECHECK_PROMPT = """你是一个技术分析预筛助手。请分析最近的K线，判断是否值得进一步分析。

## 策略入场规则
{entry_rules}

## 最近 {kline_count} 根K线
{recent_klines}

## 技术指标
{indicators}

请判断：最近K线是否出现了符合策略入场规则条件的信号？
仅输出 JSON 格式：
{{"should_analyze": true/false, "reason": "判断理由（一句话）"}}

注意：
- 只输出 JSON，不要输出其他文字
- 有明确的入场信号才返回 true，模糊信号返回 false
- 宁可漏过，不可误判（控制 false positive）
"""
```

#### 3.4.4 主循环中的逻辑

```python
# 第一级：AI 粗略预筛（两种模式）
if ctx.use_local_model:
    # 模式 B：本地模型预筛
    local_window = kline_data[-ctx.local_model_klines:]
    should_analyze = await local_prechecker.precheck(
        kline_window=local_window,
        strategy_rules=ctx.strategy_rules,
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
    )
else:
    # 模式 A：主 AI 粗略预筛（默认）
    quick_window = kline_data[-ctx.local_model_klines:]
    should_analyze = await analyzer.quick_precheck(
        kline_window=quick_window,
        strategy_rules=ctx.strategy_rules,
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
    )

if should_analyze:
    # 第二级：AI 深度分析（最多 300 根）
    window_start = max(0, len(kline_data) - AI_ANALYSIS_MAX_WINDOW)
    kline_window = kline_data[window_start:]
    ai_result = await analyzer.analyze_with_window(
        kline_window=kline_window,
        # ...
    )
else:
    # 第一级判断不满足条件，直接跳过
    ai_result = None
```

### 3.5 K 线窗口预热

```python
# 预热数据量（不变）
PREHEAT_COUNT = 300

# 第一级预筛使用的最近 K 线数
QUICK_CHECK_WINDOW = 10

# AI 分析最大窗口
AI_ANALYSIS_MAX_WINDOW = 300
```

---

## 4. 数据流图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI 回测主循环                                      │
│                                                                         │
│  ┌──────────────────────┐                                               │
│  │  加载配置 & 预热数据   │                                               │
│  └──────────┬───────────┘                                               │
│             ▼                                                           │
│  ┌──────────────────────┐    ┌──────────────────────────────────────┐   │
│  │  逐根 K 线推进循环    │───▶│  检查停止信号 (Redis)                  │   │
│  └──────────┬───────────┘    └──────────────────────────────────────┘   │
│             ▼                                                           │
│  ┌──────────────────────────────┐                                       │
│  │  有持仓？                    │                                       │
│  │  ├─ 是 → 跳过 AI 分析        │                                       │
│  │  │     → 检查止损止盈/规则     │                                       │
│  │  │     → 平仓? → 清除持仓     │                                       │
│  │  └─ 否 → 继续下一级           │                                       │
│  └──────────┬───────────────────┘                                       │
│             ▼                                                           │
│  ┌──────────────────────────────┐                                       │
│  │  第一级：AI 粗略预筛           │                                       │
│  │  ├─ [默认] 主AI Provider      │                                       │
│  │  │  (可配置 5-50 根 K 线)      │                                       │
│  │  ├─ [可选] 本地 Ollama 模型    │                                       │
│  │  │  (可配置 5-50 根 K 线)      │                                       │
│  │  └─ 两种模式互斥，配置切换      │                                       │
│  │  ├─ 满足条件 → 触发第二级      │                                       │
│  │  └─ 不满足 → 直接跳过         │                                       │
│  └──────────┬───────────────────┘                                       │
│             ▼                                                           │
│  ┌──────────────────────────────┐                                       │
│  │  第二级：AI 深度分析           │                                       │
│  │  (最近 300 根 K 线)           │                                       │
│  │  → 决策：开仓/持有             │                                       │
│  │  → 开仓 → 记录持仓，暂停 AI    │                                       │
│  └──────────────────────────────┘                                       │
│                                                                         │
│  ┌──────────────────────────────┐                                       │
│  │  回测完成 → 结果展示           │                                       │
│  │  → 单个回测 AI 分析            │                                       │
│  │  → 单个回测策略优化            │                                       │
│  │  → 多回测融合优化             │                                       │
│  └──────────────────────────────┘                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 数据库变更

### 5.1 AIBacktest 表

```python
# 新增字段
parent_backtest_id: Optional[uuid.UUID] = Field(
    None, description="父回测 ID（多策略融合时使用）"
)
strategy_ids: Optional[List[uuid.UUID]] = Field(
    None, description="参与回测的策略 ID 列表（多策略融合时）"
)
use_local_model: bool = Field(
    False, description="使用本地模型进行预筛"
)
local_model_klines: int = Field(
    10, description="本地模型分析的 K 线数量"
)
```

### 5.2 AIBacktestTrade 表

```python
# 新增字段
ai_window_start: Optional[int] = Field(
    None, description="AI 分析时使用的 K 线窗口起始索引"
)
ai_window_end: Optional[int] = Field(
    None, description="AI 分析时使用的 K 线窗口结束索引"
)
```

---

## 6. Prompt 设计

### 6.1 AI 深度分析 Prompt（窗口限制）

```
你是一个专业的加密货币交易AI助手，正在辅助用户进行策略回测。

当前回测信息：
- 策略类型：{strategy_category}
- 交易对：{symbol}
- 时间周期：{timeframe}
- 当前已推进：第 {current_kline_index} 根 / 共 {total_klines} 根
- K线窗口：最近 {window_size} 根（从 {window_start} 到 {window_end}）

最近K线数据摘要：
{kline_summary}

技术指标：
{indicators_summary}

{position_status}

策略规则摘要：
{strategy_rules}

请分析上述K线窗口中的市场状态，并给出交易决策。
{output_format}
```

### 6.2 多策略融合 Prompt

```
你是一个专业的量化交易策略融合专家。请综合以下多个策略的回测结果，融合生成一个全新的最优策略。

## 策略列表

### 策略 1：{name1}
类型：{category1}
规则：{rules1}
回测结果：{summary1}

### 策略 2：{name2}
类型：{category2}
规则：{rules2}
回测结果：{summary2}

...

## 融合要求
1. 取各策略的优势，摒弃劣势
2. 融合后的策略必须逻辑自洽，规则之间不冲突
3. 必须包含三条默认前提规则（单仓、止损、严格执规）
4. 输出完整的策略规则（入场、出场、仓位管理、风控）

请输出融合后的新策略 JSON 格式。
```

---

## 7. 性能预估

### 7.1 AI 调用次数对比

| 场景                        | 优化前  | 优化后 | 节省  |
| --------------------------- | ------- | ------ | ----- |
| 300 根 K 线，10 次信号触发  | 300 次  | 10 次  | 96.7% |
| 500 根 K 线，15 次信号触发  | 500 次  | 15 次  | 97%   |
| 1000 根 K 线，20 次信号触发 | 1000 次 | 20 次  | 98%   |

### 7.2 回测耗时对比

假设每次 AI 调用耗时 5 秒：

| 场景         | 优化前  | 优化后  | 加速 |
| ------------ | ------- | ------- | ---- |
| 300 根 K 线  | 25 分钟 | ~1 分钟 | 25x  |
| 1000 根 K 线 | 83 分钟 | ~2 分钟 | 40x  |

---

## 8. 与现有系统的关系

### 8.1 兼容性

- **向后兼容**：优化后的系统保持现有 API 接口不变，现有回测仍然可用
- **数据兼容**：已有回测数据无需迁移，新字段为空时行为不变
- **前端兼容**：新增功能为可选增强，不影响现有页面

### 8.2 依赖关系

```
ai_backtest_tasks.py
  ├── ai_market_analyzer.py (新增 quick_precheck AI粗略预筛 + analyze_with_window 深度分析)
  ├── local_model_prechecker.py (新增 本地模型预筛器)
  ├── ai_backtest_service.py (新增 merge_optimize)
  └── models/ai_backtest.py (新增字段)
```

---

## 9. 开发排期

| 阶段     | 内容                                | 预估工时 |
| -------- | ----------------------------------- | -------- |
| P1       | 数据库模型变更 + Alembic 迁移       | 1 天     |
| P2       | 后端核心逻辑：两级过滤 + 持仓免分析 | 2 天     |
| P3       | 后端多策略融合优化                  | 1 天     |
| P4       | 前端配置表单多策略选择              | 1 天     |
| P5       | 前端进度展示优化 + 融合操作入口     | 1 天     |
| P6       | 测试 + 联调 + 文档更新              | 1 天     |
| **合计** |                                     | **7 天** |
