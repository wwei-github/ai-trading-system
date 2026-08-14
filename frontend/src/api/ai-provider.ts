import request from './request';
import type {
  ProviderListResponse,
  AddProviderRequest,
  OllamaModel,
} from '@/types';

export const aiProviderApi = {
  /** 获取所有 Provider 配置 */
  async getProviders(): Promise<ProviderListResponse> {
    const res = await request.get<ProviderListResponse>('/ai/providers');
    return res.data;
  },

  /** 添加 Provider */
  async addProvider(data: AddProviderRequest): Promise<ProviderListResponse> {
    const res = await request.post<ProviderListResponse>('/ai/providers', data);
    return res.data;
  },

  /** 删除 Provider */
  async deleteProvider(providerId: string): Promise<ProviderListResponse> {
    const res = await request.delete<ProviderListResponse>(
      `/ai/providers/${providerId}`,
    );
    return res.data;
  },

  /** 切换当前激活的 Provider */
  async activateProvider(providerId: string): Promise<ProviderListResponse> {
    const res = await request.post<ProviderListResponse>(
      `/ai/providers/${providerId}/activate`,
    );
    return res.data;
  },

  /** 获取 Ollama 可用模型列表 */
  async fetchOllamaModels(baseUrl: string): Promise<OllamaModel[]> {
    const res = await request.post<{ models: OllamaModel[] }>(
      '/ai/providers/ollama/models',
      { base_url: baseUrl },
    );
    return res.data.models;
  },
};