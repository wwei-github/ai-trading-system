import request from './request';
import type {
  Strategy,
  StrategyCreateData,
  StrategyUpdateData,
  BacktestParams,
  BacktestRecord,
  PaperTradeParams,
  LiveTradeParams,
  StrategyListParams,
} from '@/types';

export const strategyApi = {
  async getList(params: StrategyListParams = {}): Promise<Strategy[]> {
    const res = await request.get<Strategy[]>('/strategies', { params });
    return res.data;
  },

  async getDetail(id: string): Promise<Strategy> {
    const res = await request.get<Strategy>(`/strategies/${id}`);
    return res.data;
  },

  async create(data: StrategyCreateData): Promise<Strategy> {
    const res = await request.post<Strategy>('/strategies', data);
    return res.data;
  },

  async update(id: string, data: StrategyUpdateData): Promise<Strategy> {
    const res = await request.patch<Strategy>(`/strategies/${id}`, data);
    return res.data;
  },

  async delete(id: string): Promise<{ deleted: boolean }> {
    const res = await request.delete<{ deleted: boolean }>(`/strategies/${id}`);
    return res.data;
  },

  async backtest(id: string, params: BacktestParams): Promise<BacktestRecord> {
    const res = await request.post<BacktestRecord>(`/strategies/${id}/backtest`, params);
    return res.data;
  },

  async getBacktests(id: string): Promise<BacktestRecord[]> {
    const res = await request.get<BacktestRecord[]>(`/strategies/${id}/backtests`);
    return res.data;
  },

  async startPaper(id: string, params?: PaperTradeParams): Promise<unknown> {
    const res = await request.post<unknown>(`/strategies/${id}/paper-trade`, params);
    return res.data;
  },

  async startLive(id: string, params: LiveTradeParams): Promise<unknown> {
    const res = await request.post<unknown>(`/strategies/${id}/live-trade`, params);
    return res.data;
  },
};

export default strategyApi;
