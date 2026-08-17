// AI 驱动策略回测类型定义

// 策略前提规则项
export interface StrategyPrerequisiteItem {
  enabled: boolean;
  description?: string;
  default_stop_loss_pct?: number;
}

// 策略前提规则集合
export interface StrategyPrerequisites {
  single_position: StrategyPrerequisiteItem;
  mandatory_stop_loss: StrategyPrerequisiteItem & { default_stop_loss_pct: number };
  strict_execution: StrategyPrerequisiteItem;
}

// 回测模式
export type BacktestMode = 'single' | 'multi';

// 回测配置
export interface AIBacktestConfig {
  strategyId: string;
  symbol: string;
  timeframe: '15m' | '1h' | '4h' | '1d';
  startDate: string;
  mode: 'kline_count' | 'time_span';
  klineCount: number;
  timeSpanValue: number;
  timeSpanUnit: 'hour' | 'day';
  initialCapital: number;
  feeRate: number;
  useAI: boolean;
  prerequisites?: StrategyPrerequisites;
  // 新增：多策略
  backtestMode?: BacktestMode;
  strategyIds?: string[];
  // 新增：本地模型辅助
  useLocalModel?: boolean;
  localModelKlines?: number;
  // 新增：Prompt 模板
  promptTemplateIds?: Record<string, string | null>;
}

// 创建回测请求
export interface AIBacktestCreateRequest {
  strategy_id: string;
  symbol: string;
  timeframe: string;
  start_time: string;
  mode: string;
  kline_count?: number;
  time_span_value?: number;
  time_span_unit?: string;
  initial_capital: number;
  fee_rate: number;
  use_ai: boolean;
  prerequisites?: StrategyPrerequisites;
  // 新增：多策略
  strategy_ids?: string[];
  // 新增：本地模型辅助
  use_local_model?: boolean;
  local_model_klines?: number;
  // 新增：Prompt 模板
  prompt_template_ids?: Record<string, string | null>;
}

// 创建回测响应
export interface AIBacktestCreateResponse {
  id: string;
  strategy_id: string;
  strategy_name: string;
  symbol: string;
  timeframe: string;
  start_time: string;
  end_time: string | null;
  mode: string;
  kline_count: number | null;
  time_span_value: number | null;
  time_span_unit: string | null;
  initial_capital: number;
  fee_rate: number;
  use_ai: boolean;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelling' | 'cancelled';
  total_klines: number;
  completed_klines: number;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  result_summary: AIBacktestSummary | null;
  created_at: string;
}

// 回测详情
export interface AIBacktestDetail {
  id: string;
  strategy_id: string;
  strategy_name: string;
  symbol: string;
  timeframe: string;
  start_time: string;
  end_time?: string;
  mode: string;
  kline_count?: number;
  initial_capital: number;
  fee_rate: number;
  use_ai: boolean;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelling' | 'cancelled';
  total_klines: number;
  completed_klines: number;
  progress: number;
  started_at?: string;
  completed_at?: string;
  result_summary?: AIBacktestSummary;
  created_at: string;
  // 新增
  ai_call_count?: number;
  precheck_total?: number;
  precheck_triggered?: number;
  use_local_model?: boolean;
  local_model_klines?: number;
  parent_backtest_id?: string;
  strategy_ids?: string[];
  initial_analysis?: InitialAnalysis;
  ai_analysis_logs?: AIAnalysisLogItem[];
  prompt_template_ids?: Record<string, string | null>;
}

// 总结指标
export interface AIBacktestSummary {
  total_trades: number;
  total_pnl: number;
  total_return_pct: number;
  win_rate: number;
  max_single_profit: number;
  max_single_loss: number;
  avg_pnl: number;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  max_drawdown_pct: number;
  final_equity: number;
  total_fee: number;
  avg_holding_bars: number;
  ai_calls: number;
  open_count: number;
  close_reasons: Record<string, number>;
  ai_analysis?: AIBacktestAnalysisResult;
}

// 交易明细
export interface AIBacktestTrade {
  id: string;
  index: number;
  direction: 'long' | 'short';
  entry_time: string;
  entry_price: number;
  quantity: number;
  open_ai_analysis?: string;
  open_reason?: string;
  open_confidence?: number;
  stop_loss?: number;
  take_profit?: number;
  exit_time?: string;
  exit_price?: number;
  exit_reason?: string;
  exit_ai_analysis?: string;
  exit_confidence?: number;
  holding_bars?: number;
  pnl?: number;
  pnl_pct?: number;
  fee?: number;
  created_at: string;
}

// AI 实时分析（SSE 推送）
export interface AIBacktestAIAnalysis {
  trend: 'bullish' | 'bearish' | 'neutral';
  strength: number;
  summary: string;
  decision: 'open_long' | 'open_short' | 'close_long' | 'close_short' | 'hold';
  confidence: number;
  reason: string;
}

// 进度推送
export interface AIBacktestProgress {
  backtest_id: string;
  stage: 'preheat' | 'running' | 'summary' | 'done' | 'error' | 'cancelled';
  progress: number;
  current_kline: number;
  total_klines: number;
  current_trades: number;
  current_position?: {
    has_position: boolean;
    direction?: string;
    entry_price?: number;
    quantity?: number;
    unrealized_pnl?: number;
    unrealized_pnl_pct?: number;
    stop_loss?: number;
    take_profit?: number;
  };
  message: string;
  ai_analysis?: AIBacktestAIAnalysis;
  indicators?: {
    ma5: number;
    ma10: number;
    rsi_14: number;
    ema20?: number;
    ema50?: number;
    volume_ma20?: number;
  };
  // 新增：预筛统计
  precheck_total?: number;
  precheck_triggered?: number;
  ai_call_count?: number;
  precheck_mode?: string;
  has_position?: boolean;
  current_equity?: number;
  initial_capital?: number;
  ai_analysis_paused?: boolean;
  analysis_window?: { start: number; end: number; size: number };
  trigger_reason?: string;
  // 新增：K 线窗口 + 事件
  kline_window?: Array<{ open: number; high: number; low: number; close: number; volume: number; time: string }>;
  current_kline_index?: number;
  latest_trade?: LatestTradeEvent;
  closed_trade?: ClosedTradeEvent;
  ai_analysis_mini?: AIAnalysisMini;
  key_levels?: KeyLevel[];
  trend?: 'bullish' | 'bearish' | 'neutral';
  initial_analysis?: InitialAnalysis;
}

// 回测结果 AI 分析响应
export interface AIBacktestAnalysisResult {
  overall_assessment: string;
  strengths: string[];
  weaknesses: string[];
  market_adaptability: {
    trend_market: string;
    range_market: string;
    volatile_market: string;
  };
  improvement_suggestions: string[];
  score: number;
}

// 策略优化结果
export interface AIBacktestOptimizeResult {
  id: string;
  name: string;
  rules: Record<string, any>;
}

// 历史列表项
export interface AIBacktestHistoryItem {
  id: string;
  strategy_name: string;
  strategy_names: string[];
  symbol: string;
  timeframe: string;
  status: string;
  total_klines: number;
  completed_klines: number;
  initial_capital: number;
  total_pnl?: number;
  win_rate?: number;
  trade_count: number;
  created_at: string;
  completed_at?: string;
}

// ==================== 新增类型 ====================

// 关键位
export interface KeyLevel {
  type: 'support' | 'resistance';
  price: number;
  hit_price?: number;
  distance_pct?: number;
}

// 开单事件
export interface LatestTradeEvent {
  id: string;
  direction: 'long' | 'short';
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  quantity: number;
  created_at: string;
}

// 平仓事件
export interface ClosedTradeEvent {
  id: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  reason: 'stop_loss' | 'take_profit' | 'manual' | 'rule';
  closed_at: string;
}

// AI 深度分析摘要（SSE推送）
export interface AIAnalysisMini {
  trend: 'bullish' | 'bearish' | 'neutral';
  key_levels: KeyLevel[];
  decision: 'open_long' | 'open_short' | 'close_long' | 'close_short' | 'hold';
  confidence: number;
  reasoning: string;
}

// 深度分析日志
export interface AIAnalysisLogItem {
  kline_index: number;
  trigger: string;
  trigger_reason: string;
  analysis: {
    trend?: string;
    summary?: string;
    reasoning?: string;
    decision?: string;
    confidence?: number;
    key_levels?: KeyLevel[];
    stop_loss?: number;
    take_profit?: number;
    stop_loss_method?: string;
    risk_reward_ratio?: number;
  };
  skipped?: boolean;
  precheck?: boolean;
  had_position?: boolean;
  created_at: string;
  // 开单/平仓详情
  trade_info?: TradeInfo;
}

// 开单/平仓详情
export interface TradeInfo {
  type: 'opened' | 'closed';
  direction: string;
  entry_price: number;
  quantity: number;
  stop_loss?: number;
  take_profit?: number;
  open_confidence?: number;
  risk_reward_ratio?: number;
  source_strategy?: string;
  // 平仓专用
  exit_price?: number;
  pnl?: number;
  pnl_pct?: number;
  holding_bars?: number;
  exit_reason?: string;
}

// 初始化分析结果
export interface InitialAnalysis {
  trend: 'bullish' | 'bearish' | 'neutral';
  trend_summary: string;
  key_levels: KeyLevel[];
}

// 回测效能统计
export interface AIBacktestEfficiency {
  ai_call_count: number;
  precheck_total: number;
  precheck_triggered: number;
  precheck_efficiency: number;
  estimated_saved_calls: number;
}

// 融合优化请求（对齐后端 schemas/ai_backtest.py::MergeOptimizeRequest）
// 路径: POST /strategies/ai-backtest/{backtest_id}/merge-optimize
export interface MergeOptimizeRequest {
  /** 父回测 ID（路径参数,提交时透传） */
  backtest_id: string;
  /** 参与融合的策略 ID 列表,至少 2 个 */
  strategy_ids: string[];
  /** 交易对,默认 BTC/USDT */
  symbol: string;
  /** 时间周期: 15m/1h/4h/1d,默认 15m */
  timeframe: '15m' | '1h' | '4h' | '1d';
  /** 新策略名称,留空自动生成 */
  name?: string;
  /** 新策略描述 */
  description?: string;
}

// 融合优化结果（对齐 docs/api/15-ai-backtest.md §10）
export interface MergeOptimizeResult {
  id: string;
  strategy_id: string;
  strategy_name: string;
  parent_backtest_id: string;
  strategy_ids: string[];
  status: string;
  symbol: string;
  timeframe: string;
  total_klines: number;
  completed_klines: number;
  progress: number;
  created_at: string;
}

// 多策略回测创建结果（后端 /multi 接口未实现,保留类型供未来使用）
export interface MultiBacktestCreateResult {
  backtests: Array<{
    id: string;
    strategy_id: string;
    strategy_name: string;
    status: string;
  }>;
}

// Prompt 模板（对齐后端 schemas/prompt_template.py::PromptTemplateResponse）
// 注意: 后端仅支持 3 类: initial_analysis / backtest_precheck / deep_analysis
export interface PromptTemplate {
  id: string;
  category: 'initial_analysis' | 'backtest_precheck' | 'deep_analysis';
  name: string;
  content: string;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at?: string | null;
}

// Prompt 模板列表项（简化版,无 content）
export interface PromptTemplateListItem {
  id: string;
  category: 'initial_analysis' | 'backtest_precheck' | 'deep_analysis';
  name: string;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at?: string | null;
}

// Prompt 模板列表响应
export interface PromptTemplateListResponse {
  items: PromptTemplateListItem[];
  total: number;
}

// 创建 Prompt 模板请求
export interface PromptTemplateCreateRequest {
  category: 'initial_analysis' | 'backtest_precheck' | 'deep_analysis';
  name: string;
  content: string;
  is_active?: boolean;
}

// 更新 Prompt 模板请求（PATCH,所有字段可选）
export interface PromptTemplateUpdateRequest {
  name?: string;
  content?: string;
  is_active?: boolean;
}