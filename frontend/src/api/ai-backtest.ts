import request from './request';
import type {
  AIBacktestCreateRequest,
  AIBacktestCreateResponse,
  AIBacktestDetail,
  AIBacktestTrade,
  AIBacktestHistoryItem,
} from '@/types';

export const aiBacktestApi = {
  /** 创建并启动 AI 回测 */
  create: (data: AIBacktestCreateRequest) =>
    request.post<AIBacktestCreateResponse>('/strategies/ai-backtest', data),

  /** 获取回测详情 */
  getDetail: (id: string) =>
    request.get<AIBacktestDetail>(`/strategies/ai-backtest/${id}`),

  /** 获取交易明细（分页） */
  getTrades: (id: string, page: number = 1, pageSize: number = 20) =>
    request.get<{
      items: AIBacktestTrade[];
      total: number;
      page: number;
      page_size: number;
    }>(`/strategies/ai-backtest/${id}/trades`, {
      params: { page, page_size: pageSize },
    }),

  /** 获取历史列表 */
  getHistory: (page: number = 1, pageSize: number = 10) =>
    request.get<{
      items: AIBacktestHistoryItem[];
      total: number;
      page: number;
      page_size: number;
    }>('/strategies/ai-backtest/list', {
      params: { page, page_size: pageSize },
    }),

  /** 取消回测 */
  cancel: (id: string) =>
    request.post(`/strategies/ai-backtest/${id}/cancel`),

  /** 获取 SSE 进度 URL */
  getProgressUrl: (id: string) =>
    `/api/v1/strategies/ai-backtest/${id}/progress`,
};

export default aiBacktestApi;