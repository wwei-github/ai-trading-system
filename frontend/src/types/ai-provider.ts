/** 本地模型（Ollama）配置 */
export interface LocalModelConfig {
  model: string;
  temperature: number;
  max_tokens: number;
  embedding_model?: string;
  base_url?: string;
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
