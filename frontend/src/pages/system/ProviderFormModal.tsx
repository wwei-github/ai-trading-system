import { useState, useEffect } from 'react';
import {
  Modal, Form, Input, Select, Slider, InputNumber, Button, message, Space, Alert,
} from 'antd';
import { aiProviderApi } from '@/api/ai-provider';
import type { AIProvider, ProviderType, OllamaModel } from '@/types';

interface Props {
  open: boolean;
  provider: AIProvider | null;
  onClose: () => void;
  onSuccess: () => void;
}

const PROVIDER_TYPES: { value: ProviderType; label: string }[] = [
  { value: 'openai_compatible', label: 'OpenAI 兼容接口' },
  { value: 'ollama', label: 'Ollama 本地模型' },
];

const DEFAULT_CONFIG: Record<string, any> = {
  openai_compatible: {
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    temperature: 0.7,
    max_tokens: 2000,
  },
  ollama: {
    base_url: 'http://localhost:11434',
    model: 'qwen3.5:9b',
    temperature: 0.7,
    max_tokens: 4096,
  },
};

const ProviderFormModal = ({ open, provider, onClose, onSuccess }: Props) => {
  const [form] = Form.useForm();
  const [type, setType] = useState<ProviderType>('openai_compatible');
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [fetching, setFetching] = useState(false);

  const isEdit = !!provider;

  useEffect(() => {
    if (open) {
      if (provider) {
        setType(provider.type);
        form.setFieldsValue({
          type: provider.type,
          name: provider.name,
          ...provider.config,
        });
      } else {
        setType('openai_compatible');
        form.resetFields();
        form.setFieldsValue({ type: 'openai_compatible' });
      }
      setOllamaModels([]);
    }
  }, [open, provider, form]);

  const handleTypeChange = (value: ProviderType) => {
    setType(value);
    form.setFieldsValue(DEFAULT_CONFIG[value] || {});
    setOllamaModels([]);
  };

  const handleFetchOllamaModels = async () => {
    const baseUrl = form.getFieldValue('base_url');
    if (!baseUrl) {
      message.warning('请先填写接口地址');
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
      const errMsg = e?.message || '';
      if (errMsg.includes('connect') || errMsg.includes('ECONNREFUSED')) {
        message.error('连接 Ollama 失败，请检查 Ollama 服务是否已启动');
      } else if (errMsg.includes('timeout')) {
        message.error('连接超时，请检查网络和地址是否正确');
      } else {
        message.error('无法连接到该地址，请确认接口地址正确');
      }
    } finally {
      setFetching(false);
    }
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    const payload = {
      type,
      name: values.name,
      config: {
        base_url: values.base_url,
        model: values.model,
        temperature: values.temperature ?? 0.7,
        max_tokens: values.max_tokens ?? (type === 'ollama' ? 4096 : 2000),
      },
    };

    try {
      await aiProviderApi.addProvider(payload);
      message.success(isEdit ? '更新成功' : '添加成功');
      onSuccess();
    } catch (e: any) {
      message.error('操作失败: ' + (e?.message || '未知错误'));
    }
  };

  return (
    <Modal
      title={isEdit ? '编辑 Provider' : '添加 Provider'}
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      width={560}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" initialValues={{ type: 'openai_compatible' }}>
        <Form.Item label="类型" name="type" rules={[{ required: true }]}>
          <Select onChange={handleTypeChange} options={PROVIDER_TYPES} />
        </Form.Item>

        <Form.Item
          label="名称"
          name="name"
          rules={[{ required: true, message: '请输入自定义名称以便识别' }]}
        >
          <Input placeholder="如：OpenAI GPT-4o、Ollama 本地" />
        </Form.Item>

        <Alert
          type="info"
          showIcon
          message="API Key 通过环境变量配置"
          description="API Key 完全通过环境变量 LLM_API_KEY 配置，不在 UI 中填写或展示。修改环境变量后需重启服务生效。"
          style={{ marginBottom: 16 }}
        />

        <Form.Item
          label="接口地址"
          name="base_url"
          rules={[{ required: true, message: '请输入接口地址' }]}
        >
          <Input
            placeholder={
              type === 'ollama'
                ? 'http://localhost:11434'
                : 'https://api.openai.com/v1'
            }
          />
        </Form.Item>

        <Form.Item label="模型" name="model" rules={[{ required: true }]}>
          {type === 'ollama' ? (
            <Space style={{ width: '100%' }}>
              <Select
                style={{ flex: 1 }}
                placeholder="选择模型或手动输入"
                options={ollamaModels.map((m) => ({
                  value: m.name,
                  label: `${m.name} (${(m.size / 1e9).toFixed(1)}GB)`,
                }))}
              />
              <Button onClick={handleFetchOllamaModels} loading={fetching}>
                获取模型列表
              </Button>
            </Space>
          ) : (
            <Input placeholder="gpt-4o-mini" />
          )}
        </Form.Item>

        <Form.Item label="Temperature" name="temperature">
          <Slider min={0} max={2} step={0.1} />
        </Form.Item>

        <Form.Item label="Max Tokens" name="max_tokens">
          <InputNumber min={1} max={128000} style={{ width: '100%' }} />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default ProviderFormModal;