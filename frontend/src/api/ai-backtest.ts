import request from './request';
import type {
  AIBacktestCreateRequest,
  AIBacktestCreateResponse,
  AIBacktestDetail,
  AIBacktestTrade,
  AIBacktestHistoryItem,
  AIBacktestAnalysisResult,
  AIBacktestOptimizeResult,
  MergeOptimizeRequest,
  MergeOptimizeResult,
  MultiBacktestCreateResult,
  PromptTemplate,
} from '@/types';

export const aiBacktestApi = {
  /** 创建并启动 AI 回测 */
  create: (data: AIBacktestCreateRequest) =>
    request.post<AIBacktestCreateResponse>('/strategies/ai-backtest', data),

  /** 创建多策略回测 */
  createMulti: (data: AIBacktestCreateRequest & { strategy_ids: string[] }) =>
    request.post<MultiBacktestCreateResult>('/strategies/ai-backtest/multi', data),

  /** 多策略融合优化 */
  mergeOptimize: (data: MergeOptimizeRequest) =>
    request.post<MergeOptimizeResult>('/strategies/ai-backtest/merge-optimize', data),

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

  /** 终止运行中的回测 */
  stop: (id: string) =>
    request.post(`/strategies/ai-backtest/${id}/stop`),

  /** AI 分析回测结果 */
  analyze: (id: string) =>
    request.post<AIBacktestAnalysisResult>(`/strategies/ai-backtest/${id}/analyze`),

  /** 基于回测结果优化策略 */
  optimize: (id: string) =>
    request.post<AIBacktestOptimizeResult>(`/strategies/ai-backtest/${id}/optimize`),

  /** 获取 SSE 进度 URL */
  getProgressUrl: (id: string) =>
    `/api/v1/strategies/ai-backtest/${id}/progress`,
};

// Prompt 模板 API
export const promptTemplateApi = {
  /** 获取模板列表 */
  list: (category?: string) =>
    request.get<PromptTemplate[]>('/prompt-templates', { params: { category } }),

  /** 创建模板 */
  create: (data: Pick<PromptTemplate, 'name' | 'category' | 'content' | 'description' | 'variables'>) =>
    request.post<PromptTemplate>('/prompt-templates', data),

  /** 更新模板 */
  update: (id: string, data: Partial<Pick<PromptTemplate, 'name' | 'content' | 'description' | 'variables'>>) =>
    request.put<PromptTemplate>(`/prompt-templates/${id}`, data),

  /** 删除模板 */
  remove: (id: string) =>
    request.delete<boolean>(`/prompt-templates/${id}`),

  /** 设为默认 */
  setDefault: (id: string) =>
    request.post<PromptTemplate>(`/prompt-templates/${id}/set-default`),
};

export default aiBacktestApi;