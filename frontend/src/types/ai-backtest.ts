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
  status: 'pending' | 'running' | 'completed' | 'failed';
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
  status: 'pending' | 'running' | 'completed' | 'failed';
  total_klines: number;
  completed_klines: number;
  progress: number;
  started_at?: string;
  completed_at?: string;
  result_summary?: AIBacktestSummary;
  created_at: string;
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

// 进度推送
export interface AIBacktestProgress {
  backtest_id: string;
  stage: 'preheat' | 'running' | 'summary' | 'done' | 'error';
  progress: number;
  current_kline: number;
  total_klines: number;
  current_trades: number;
  current_position?: {
    has_position: boolean;
    direction?: string;
    entry_price?: number;
    unrealized_pnl?: number;
  };
  message: string;
}

// 历史列表项
export interface AIBacktestHistoryItem {
  id: string;
  strategy_name: string;
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