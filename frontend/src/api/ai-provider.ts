import request from './request';
import type { LocalModelConfig, OllamaModel } from '@/types';

export const aiProviderApi = {
  /** 获取本地模型配置 */
  async getLocalModel(): Promise<LocalModelConfig> {
    const res = await request.get<LocalModelConfig>('/ai/providers/local-model');
    return res.data;
  },

  /** 更新本地模型配置 */
  async updateLocalModel(
    data: Partial<LocalModelConfig>,
  ): Promise<LocalModelConfig> {
    const res = await request.patch<LocalModelConfig>(
      '/ai/providers/local-model',
      data,
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
