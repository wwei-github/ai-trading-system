// 统计概览数据
export interface OverviewData {
  total_asset: number;
  available_balance: number;
  frozen_balance: number;
  today_profit: number;
  total_profit: number;
  today_trade_count: number;
  today_trade_amount: number;
  active_coin_count: number;
  win_rate: number;
}

// 收益趋势数据点
export interface ProfitTrendPoint {
  date: string;
  total_asset: number;
  profit: number;
  profit_rate: number;
}

// 收益趋势查询参数
export interface ProfitTrendParams {
  range?: '7d' | '30d' | '90d' | '1y' | 'custom';
  start_date?: string;
  end_date?: string;
  account_id?: number;
}

// 资产分布项
export interface AssetDistributionItem {
  name: string;
  value: number;
  percentage: number;
}

// 交易统计
export interface TradeStatsData {
  buy_count: number;
  sell_count: number;
  buy_amount: number;
  sell_amount: number;
  symbol_stats: Array<{ symbol: string; count: number; amount: number }>;
}

// 币种排行项
export interface CoinRankingItem {
  symbol: string;
  total_profit: number;
  trade_count: number;
  win_rate: number;
  profit_rate: number;
}

// 月度报表项
export interface MonthlyReportItem {
  month: string;
  profit: number;
  trade_count: number;
  win_rate: number;
}

// 胜率走势点
export interface WinRateTrendPoint {
  date: string;
  win_rate: number;
  trade_count: number;
}

// 回撤曲线点
export interface DrawdownPoint {
  date: string;
  drawdown: number;
  max_drawdown: number;
}

// 盈亏分布项
export interface ProfitDistributionItem {
  range: string;
  count: number;
}

// 统计查询基础参数
export interface StatsQueryParams {
  start_date?: string;
  end_date?: string;
  account_id?: number;
  exchange?: string;
}
