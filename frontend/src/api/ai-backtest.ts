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
  PromptTemplate,
  PromptTemplateListResponse,
  PromptTemplateCreateRequest,
  PromptTemplateUpdateRequest,
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

  /** 终止运行中的回测 */
  stop: (id: string) =>
    request.post(`/strategies/ai-backtest/${id}/stop`),

  /** AI 分析回测结果 */
  analyze: (id: string) =>
    request.post<AIBacktestAnalysisResult>(`/strategies/ai-backtest/${id}/analyze`),

  /** 基于回测结果优化策略 */
  optimize: (id: string) =>
    request.post<AIBacktestOptimizeResult>(`/strategies/ai-backtest/${id}/optimize`),

  /**
   * 多策略融合优化
   * 路径: POST /strategies/ai-backtest/{backtest_id}/merge-optimize
   * 请求体: strategy_ids / symbol / timeframe / name / description
   */
  mergeOptimize: (backtestId: string, data: Omit<MergeOptimizeRequest, 'backtest_id'>) =>
    request.post<MergeOptimizeResult>(
      `/strategies/ai-backtest/${backtestId}/merge-optimize`,
      data,
    ),

  /** 获取 SSE 进度 URL */
  getProgressUrl: (id: string) =>
    `/api/v1/strategies/ai-backtest/${id}/progress`,
};

/**
 * Prompt 模板 API
 *
 * 注意:
 * - 路径前缀为 /ai/prompt-templates (挂在 ai 路由下)
 * - 后端仅支持 3 类: initial_analysis / backtest_precheck / deep_analysis
 * - 更新使用 PATCH 方法,非 PUT
 * - 当前后端未实现 set-default 接口
 */
export const promptTemplateApi = {
  /** 获取模板列表 */
  list: (params?: { category?: string; active_only?: boolean }) =>
    request.get<PromptTemplateListResponse>('/ai/prompt-templates', { params }),

  /** 获取模板详情 */
  get: (id: string) =>
    request.get<PromptTemplate>(`/ai/prompt-templates/${id}`),

  /** 创建模板 */
  create: (data: PromptTemplateCreateRequest) =>
    request.post<PromptTemplate>('/ai/prompt-templates', data),

  /** 更新模板（PATCH,版本号自动 +1） */
  update: (id: string, data: PromptTemplateUpdateRequest) =>
    request.patch<PromptTemplate>(`/ai/prompt-templates/${id}`, data),

  /** 删除模板 */
  remove: (id: string) =>
    request.delete<{ status: string }>(`/ai/prompt-templates/${id}`),
};

export default aiBacktestApi;