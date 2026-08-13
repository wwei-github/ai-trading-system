import request from './request';
import type {
  Trade,
  TradeFormData,
  TradeListParams,
  BatchImportResult,
  PaginatedResponse,
} from '@/types';

export const tradeApi = {
  /** 获取交易记录分页列表 */
  async getList(params: TradeListParams = {}): Promise<PaginatedResponse<Trade>> {
    const res = await request.get<PaginatedResponse<Trade>>('/trades', { params });
    return res.data;
  },

  /** 获取交易详情 */
  async getDetail(id: string): Promise<Trade> {
    const res = await request.get<Trade>(`/trades/${id}`);
    return res.data;
  },

  /** 批量导入交易记录 */
  async batchImport(accountId: string, trades: TradeFormData[]): Promise<BatchImportResult> {
    const res = await request.post<BatchImportResult>('/trades/import', {
      account_id: accountId,
      trades,
    });
    return res.data;
  },

  /** 更新交易标签/备注 */
  async updateTags(id: string, data: { tags?: string[]; note?: string }): Promise<Trade> {
    const res = await request.patch<Trade>(`/trades/${id}/tags`, data);
    return res.data;
  },

  /** 导出交易记录 */
  async exportTrades(params: TradeListParams = {}, fmt: 'csv' | 'json' = 'csv'): Promise<Blob> {
    const res = await request.get('/trades/export', {
      params: { ...params, fmt },
      responseType: 'blob',
    });
    return res as unknown as Blob;
  },
};

export default tradeApi;
