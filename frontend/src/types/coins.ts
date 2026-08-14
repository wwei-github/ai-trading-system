export interface Coin {
  id: string;
  symbol: string;
  name?: string;
  current_price?: number;
  price_change_24h?: number;
  volume_24h?: number;
}

export interface CoinTicker {
  symbol: string;
  name?: string;
  current_price?: number;
  price_change_24h?: number;
  volume_24h?: number;
}

export interface KlinePoint {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface IndicatorData {
  symbol: string;
  timeframe: string;
  indicators: Record<string, number>;
  signal?: string;
  updated_at?: string;
}

export interface CoinListParams {
  limit?: number;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export type KlinePeriod = '1m' | '5m' | '15m' | '1h' | '4h' | '1d' | '1w';

export interface KlineParams {
  symbol: string;
  period?: KlinePeriod;
  limit?: number;
}

export interface CompareParams {
  symbols: string[];
  period?: KlinePeriod;
  days?: number;
}

export interface CompareResultItem {
  info?: CoinTicker;
  analysis?: IndicatorData;
  symbol?: string;
  error?: string;
}
