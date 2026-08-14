import request from './request';
import type {
  Coin,
  CoinTicker,
  KlinePoint,
  IndicatorData,
  CoinListParams,
  KlineParams,
  CompareParams,
  CompareResultItem,
} from '@/types';

export const coinApi = {
  async getList(params: CoinListParams = {}): Promise<Coin[]> {
    const query = new URLSearchParams();
    if (params.limit) query.append('limit', String(params.limit));
    if (params.search) query.append('search', params.search);
    if (params.sort_by) query.append('sort_by', params.sort_by);
    if (params.sort_order) query.append('sort_order', params.sort_order);
    const qs = query.toString();
    const res = await request.get<Coin[]>(`/coins${qs ? `?${qs}` : ''}`);
    return res.data;
  },

  async getDetail(symbol: string): Promise<CoinTicker> {
    const res = await request.get<CoinTicker>(`/coins/${encodeURIComponent(symbol)}`);
    return res.data;
  },

  async getTicker(symbol: string): Promise<CoinTicker> {
    const res = await request.get<CoinTicker>(`/coins/${encodeURIComponent(symbol)}/ticker`);
    return res.data;
  },

  async getKline(params: KlineParams): Promise<KlinePoint[]> {
    const query = new URLSearchParams();
    if (params.period) query.append('timeframe', params.period);
    if (params.limit) query.append('limit', String(params.limit));
    const qs = query.toString();
    const res = await request.get<KlinePoint[]>(
      `/coins/${encodeURIComponent(params.symbol)}/kline${qs ? `?${qs}` : ''}`,
    );
    return res.data;
  },

  async getIndicators(symbol: string, period?: string): Promise<IndicatorData> {
    const query = new URLSearchParams();
    if (period) query.append('timeframe', period);
    const qs = query.toString();
    const res = await request.get<IndicatorData>(
      `/coins/${encodeURIComponent(symbol)}/indicators${qs ? `?${qs}` : ''}`,
    );
    return res.data;
  },

  async compare(params: CompareParams): Promise<CompareResultItem[]> {
    const query = new URLSearchParams();
    query.append('symbols', params.symbols.join(','));
    if (params.period) query.append('timeframe', params.period);
    if (params.days) query.append('days', String(params.days));
    const qs = query.toString();
    const res = await request.get<CompareResultItem[]>(`/coins/compare${qs ? `?${qs}` : ''}`);
    return res.data;
  },
};

export default coinApi;
