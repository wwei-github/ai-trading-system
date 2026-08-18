import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Card, Form, Input, Select, Slider, InputNumber, Button, Space, message, Alert, Tag,
} from 'antd';
import {
  SaveOutlined, ReloadOutlined, ApiOutlined,
} from '@ant-design/icons';
import { aiProviderApi } from '@/api/ai-provider';
import type { LocalModelConfig, OllamaModel } from '@/types';

/**
 * 本地模型（Ollama）设置。
 *
 * 云端 AI 完全由环境变量（LLM_*）配置，此处仅管理本地预筛使用的 Ollama 模型信息。
 */
const AIProviders = () => {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<LocalModelConfig>();
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [fetching, setFetching] = useState(false);

  const { data, isLoading } = useQuery<LocalModelConfig>({
    queryKey: ['ai', 'local-model'],
    queryFn: () => aiProviderApi.getLocalModel(),
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue({
        model: data.model,
        temperature: data.temperature ?? 0.7,
        max_tokens: data.max_tokens ?? 4096,
        embedding_model: data.embedding_model,
      });
    }
  }, [data, form]);

  const updateMutation = useMutation({
    mutationFn: (values: Partial<LocalModelConfig>) =>
      aiProviderApi.updateLocalModel(values),
    onSuccess: () => {
      message.success('本地模型配置已保存');
      queryClient.invalidateQueries({ queryKey: ['ai', 'local-model'] });
    },
  });

  const handleFetchModels = async () => {
    const baseUrl = data?.base_url;
    if (!baseUrl) {
      message.warning('请先在环境变量中配置 OLLAMA_BASE_URL');
      return;
    }
    setFetching(true);
    try {
      const models = await aiProviderApi.fetchOllamaModels(baseUrl);
      setOllamaModels(models);
      if (models.length > 0) {
        message.success(`获取到 ${models.length} 个模型`);
      } else {
        message.info('未获取到可用模型，请先在 Ollama 中拉取模型');
      }
    } catch (e: any) {
      message.error('连接 Ollama 失败，请检查 Ollama 服务是否已启动');
    } finally {
      setFetching(false);
    }
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    await updateMutation.mutateAsync(values);
  };

  return (
    <div style={{ maxWidth: 720 }}>
      <Alert
        type="info"
        showIcon
        message="云端 AI 配置已迁移到环境变量"
        description="云端 AI（接口地址、模型、API Key 等）完全通过环境变量 LLM_* 配置。此处仅管理本地预筛使用的 Ollama 模型信息。"
        style={{ marginBottom: 16 }}
      />

      <Card
        title={
          <Space>
            <span>本地模型（Ollama）</span>
            {data?.base_url && (
              <Tag color="blue" icon={<ApiOutlined />}>
                {data.base_url}
              </Tag>
            )}
          </Space>
        }
        loading={isLoading}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={handleFetchModels} loading={fetching}>
              获取模型列表
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
              loading={updateMutation.isPending}
            >
              保存
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="模型名称"
            name="model"
            rules={[{ required: true, message: '请输入或选择模型名称' }]}
            tooltip="本地预筛使用的 Ollama 模型，可在 Ollama 中先拉取模型"
          >
            <Select
              placeholder="选择模型或手动输入"
              showSearch
              optionFilterProp="label"
              options={ollamaModels.map((m) => ({
                value: m.name,
                label: `${m.name} (${(m.size / 1e9).toFixed(1)}GB)`,
              }))}
              mode={undefined}
            />
          </Form.Item>

          <Form.Item label="Temperature" name="temperature">
            <Slider min={0} max={2} step={0.1} />
          </Form.Item>

          <Form.Item label="Max Tokens" name="max_tokens">
            <InputNumber min={1} max={128000} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            label="Embedding 模型"
            name="embedding_model"
            tooltip="本地向量嵌入使用的模型（可选）"
          >
            <Input placeholder="如 nomic-embed-text" />
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default AIProviders;
