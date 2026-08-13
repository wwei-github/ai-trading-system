import request from './request';
import type {
  Account,
  AccountListParams,
  AccountCreateData,
  AccountUpdateData,
  ConnectionTestResult,
} from '@/types';

export const accountApi = {
  /** 获取账号列表 */
  async getList(_params: AccountListParams = {}): Promise<Account[]> {
    const res = await request.get<Account[]>('/accounts');
    return res.data;
  },

  /** 获取账号详情 */
  async getDetail(id: string): Promise<Account> {
    const res = await request.get<Account>(`/accounts/${id}`);
    return res.data;
  },

  /** 新增账号 */
  async create(data: AccountCreateData): Promise<Account> {
    const res = await request.post<Account>('/accounts', data);
    return res.data;
  },

  /** 更新账号 */
  async update(id: string, data: AccountUpdateData): Promise<Account> {
    const res = await request.patch<Account>(`/accounts/${id}`, data);
    return res.data;
  },

  /** 删除账号 */
  async delete(id: string): Promise<void> {
    await request.delete(`/accounts/${id}`);
  },

  /** 测试交易所连接 */
  async testConnection(id: string): Promise<ConnectionTestResult> {
    const res = await request.post<ConnectionTestResult>(`/accounts/${id}/test`);
    return res.data;
  },

  /** 查询账号余额 */
  async getBalance(id: string): Promise<Record<string, unknown>> {
    const res = await request.get<Record<string, unknown>>(`/accounts/${id}/balance`);
    return res.data;
  },

  /** 触发同步 */
  async syncAccount(id: string): Promise<{ task_id: string | null; message: string }> {
    const res = await request.post<{ task_id: string | null; message: string }>(
      `/accounts/${id}/sync`,
    );
    return res.data;
  },
};

export default accountApi;
