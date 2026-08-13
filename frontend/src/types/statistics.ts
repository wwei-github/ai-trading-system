// 交易汇总统计（匹配后端 TradeSummary）
export interface OverviewData {
  total_trades: number;
  total_volume: number;
  total_fee: number;
  buy_count: number;
  sell_count: number;
  win_rate?: number;
  profit_loss?: number;
  total_asset?: number;
  available_balance?: number;
  frozen_balance?: number;
  total_profit?: number;
  today_profit?: number;
  today_trade_count?: number;
  today_trade_amount?: number;
  active_coin_count?: number;
}

// 按周期统计的盈亏（匹配后端 PnLByPeriod）
export interface ProfitTrendPoint {
  period: string;
  pnl: number;
  trade_count: number;
  date?: string;
  total_asset?: number;
}

// 资产趋势（匹配后端 AssetTrend）
export interface AssetTrendPoint {
  date: string;
  total_usd: number;
}

// 币种统计（匹配后端 CoinStat）
export interface CoinRankingItem {
  symbol: string;
  trade_count: number;
  total_volume: number;
  total_fee: number;
  net_pnl?: number;
  win_rate?: number;
}

// 收益趋势查询参数
export interface ProfitTrendParams {
  period?: 'daily' | 'weekly' | 'monthly';
  range?: '7d' | '30d' | '90d';
  start_date?: string;
  end_date?: string;
  symbol?: string;
}

// 统计查询基础参数（匹配后端 StatisticsQueryParams）
export interface StatsQueryParams {
  start_date?: string;
  end_date?: string;
  account_id?: string;
  symbol?: string;
}

// 兼容旧引用（Dashboard 中使用）
export type AssetDistributionItem = AssetTrendPoint;
export type TradeStatsData = OverviewData;
export type MonthlyReportItem = ProfitTrendPoint;
export type WinRateTrendPoint = ProfitTrendPoint;
export type DrawdownPoint = ProfitTrendPoint;
export type ProfitDistributionItem = CoinRankingItem;
