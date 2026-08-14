/** Provider 类型枚举 */
export type ProviderType = 'openai_compatible' | 'ollama';

/** Provider 配置（通用） */
export interface ProviderConfig {
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
  api_key?: string;
  embedding_model?: string;
  embedding_dimension?: number;
}

/** AI Provider 完整数据 */
export interface AIProvider {
  id: string;
  type: ProviderType;
  name: string;
  enabled: boolean;
  config: ProviderConfig;
  created_at: string;
  updated_at: string;
}

/** Provider 列表响应 */
export interface ProviderListResponse {
  active_provider_id: string | null;
  providers: AIProvider[];
}

/** 添加 Provider 请求 */
export interface AddProviderRequest {
  type: ProviderType;
  name: string;
  config: Omit<ProviderConfig, 'embedding_model' | 'embedding_dimension'> & {
    embedding_model?: string;
    embedding_dimension?: number;
  };
}

/** Ollama 模型信息 */
export interface OllamaModel {
  name: string;
  size: number;
  modified_at: string;
}

/** Ollama 模型列表响应 */
export interface OllamaModelsResponse {
  models: OllamaModel[];
}