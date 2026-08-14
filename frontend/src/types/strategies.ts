import type { PageParams } from './api';

export type StrategyStatus = 'active' | 'inactive' | 'running' | 'draft' | 'archived';

export interface Strategy {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  strategy_type: string;
  status: StrategyStatus;
  rules: Record<string, unknown>;
  risk_controls: Record<string, unknown>;
  source_book_id?: string;
  created_at: string;
  updated_at: string;
}

export interface StrategyCreateData {
  name: string;
  description?: string;
  strategy_type: string;
  rules?: Record<string, unknown>;
  risk_controls?: Record<string, unknown>;
  status?: StrategyStatus;
  source_book_id?: string;
}

export interface StrategyUpdateData {
  name?: string;
  description?: string;
  rules?: Record<string, unknown>;
  risk_controls?: Record<string, unknown>;
  status?: StrategyStatus;
}

export interface BacktestParams {
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  fee_rate?: number;
  timeframe?: string;
  strategy_id?: string;
  params?: Record<string, unknown>;
}

export interface BacktestResult {
  total_return: number;
  max_drawdown: number;
  win_rate: number;
  sharpe_ratio: number;
  total_trades: number;
  profit_factor?: number;
}

export interface BacktestRecord {
  id: string;
  strategy_id: string;
  symbol: string;
  timeframe: string;
  params: BacktestParams;
  result: BacktestResult | null;
  start_date: string;
  end_date: string;
  initial_capital: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TradeLog {
  id: string;
  strategy_id: string;
  type: string;
  message: string;
  created_at: string;
}

export interface StrategyListParams extends PageParams {
  status?: StrategyStatus;
  strategy_type?: string;
  keyword?: string;
}

export interface PaperTradeParams {
  symbol: string;
  side: string;
  amount: number;
  price?: number;
}

export interface LiveTradeParams {
  symbol: string;
  side: string;
  order_type?: string;
  amount: number;
  price?: number;
  account_id: string;
  confirm: boolean;
}
