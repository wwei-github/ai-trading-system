import request from './request';
import type {
  Coin,
  CoinTicker,
  KlinePoint,
  KlineResponse,
  IndicatorData,
  CoinListParams,
  KlineParams,
  CompareParams,
  CompareResponse,
} from '@/types';

const _sym = (s: string) => s.replace(/\//g, '-');

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
    const res = await request.get<CoinTicker>(`/coins/${_sym(symbol)}`);
    return res.data;
  },

  async getTicker(symbol: string): Promise<CoinTicker> {
    const res = await request.get<CoinTicker>(`/coins/${_sym(symbol)}/ticker`);
    return res.data;
  },

  async getKline(params: KlineParams): Promise<KlinePoint[]> {
    const query = new URLSearchParams();
    if (params.period) query.append('timeframe', params.period);
    if (params.limit) query.append('limit', String(params.limit));
    const qs = query.toString();
    // 后端返回 { code, data: { symbol, timeframe, data: KlinePoint[] } }
    const res = await request.get<KlineResponse>(
      `/coins/${_sym(params.symbol)}/kline${qs ? `?${qs}` : ''}`,
    );
    return res.data.data || [];
  },

  async getIndicators(symbol: string, period?: string): Promise<IndicatorData> {
    const query = new URLSearchParams();
    if (period) query.append('timeframe', period);
    const qs = query.toString();
    const res = await request.get<IndicatorData>(
      `/coins/${_sym(symbol)}/indicators${qs ? `?${qs}` : ''}`,
    );
    return res.data;
  },

  async compare(params: CompareParams): Promise<CompareResponse> {
    const query = new URLSearchParams();
    query.append('symbols', params.symbols.join(','));
    if (params.period) query.append('timeframe', params.period);
    if (params.days) query.append('days', String(params.days));
    const qs = query.toString();
    const res = await request.get<CompareResponse>(`/coins/compare${qs ? `?${qs}` : ''}`);
    return res.data;
  },
};

export default coinApi;
