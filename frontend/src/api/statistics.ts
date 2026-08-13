import request from './request';
import type {
  OverviewData,
  ProfitTrendPoint,
  ProfitTrendParams,
  CoinRankingItem,
  AssetTrendPoint,
  StatsQueryParams,
} from '@/types';

export const statisticsApi = {
  /** 交易汇总指标 */
  async getSummary(params: StatsQueryParams = {}): Promise<OverviewData> {
    const res = await request.get<OverviewData>('/statistics/summary', { params });
    return res.data;
  },

  /** 盈亏按周期统计 */
  async getPnl(params: ProfitTrendParams = {}): Promise<ProfitTrendPoint[]> {
    const res = await request.get<ProfitTrendPoint[]>('/statistics/pnl', { params });
    return res.data;
  },

  /** 币种维度统计 */
  async getCoinRanking(params: StatsQueryParams = {}): Promise<CoinRankingItem[]> {
    const res = await request.get<CoinRankingItem[]>('/statistics/coins', { params });
    return res.data;
  },

  /** 资产趋势 */
  async getAssetTrend(params: { account_id?: string; days?: number } = {}): Promise<AssetTrendPoint[]> {
    const res = await request.get<AssetTrendPoint[]>('/statistics/asset-trend', { params });
    return res.data;
  },

  /** 交易所分布 */
  async getExchangeDistribution(params: StatsQueryParams = {}): Promise<Record<string, number>> {
    const res = await request.get<Record<string, number>>('/statistics/exchange-distribution', { params });
    return res.data;
  },

  /** 买卖方向分布 */
  async getSideDistribution(params: StatsQueryParams = {}): Promise<Record<string, number>> {
    const res = await request.get<Record<string, number>>('/statistics/side-distribution', { params });
    return res.data;
  },

  /** 交易时间分布 */
  async getTimeDistribution(params: StatsQueryParams = {}): Promise<Record<string, number>> {
    const res = await request.get<Record<string, number>>('/statistics/time-distribution', { params });
    return res.data;
  },

  /** 策略收益对比 */
  async getStrategyComparison(): Promise<Record<string, unknown>[]> {
    const res = await request.get<Record<string, unknown>[]>('/statistics/strategy-comparison');
    return res.data;
  },

  /** 月度报表 */
  async getMonthlyReport(params: { year?: number; month?: number } = {}): Promise<Record<string, unknown>> {
    const res = await request.get<Record<string, unknown>>('/statistics/monthly-report', { params });
    return res.data;
  },

  /** 导出统计报表 */
  async exportReport(params: StatsQueryParams = {}): Promise<Blob> {
    const res = await request.get('/statistics/export', {
      params,
      responseType: 'blob',
    });
    return res as unknown as Blob;
  },
};

export default statisticsApi;
