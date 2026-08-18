import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card, Button, List, Tag, Space, Select, message, Popconfirm,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import { aiProviderApi } from '@/api/ai-provider';
import type { AIProvider, ProviderListResponse } from '@/types';
import ProviderFormModal from './ProviderFormModal';

const AIProviders = () => {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<AIProvider | null>(null);

  const { data, isLoading } = useQuery<ProviderListResponse>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProviderApi.getProviders(),
  });

  const providers = data?.providers || [];
  const activeProviderId = data?.active_provider_id;

  const activateMutation = useMutation({
    mutationFn: (id: string) => aiProviderApi.activateProvider(id),
    onSuccess: () => {
      message.success('Provider 切换成功');
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => aiProviderApi.deleteProvider(id),
    onSuccess: () => {
      message.success('Provider 已删除');
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] });
    },
  });

  const renderProviderSwitch = () => (
    <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
      <span style={{ fontWeight: 500 }}>当前使用的 Provider：</span>
      <Select
        value={activeProviderId}
        style={{ width: 300 }}
        loading={activateMutation.isPending}
        onChange={(id) => activateMutation.mutate(id)}
        placeholder="选择 Provider"
        options={providers.map((p) => ({
          value: p.id,
          label: p.name,
        }))}
      />
    </div>
  );

  const renderProviderItem = (provider: AIProvider) => {
    const isActive = provider.id === activeProviderId;
    const config = provider.config;
    return (
      <List.Item
        actions={[
          <Button
            key="edit"
            type="link"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingProvider(provider);
              setModalOpen(true);
            }}
          >
            编辑
          </Button>,
          <Popconfirm
            key="delete"
            title={isActive ? '请先切换到其他 Provider 后再删除' : '确认删除此 Provider？'}
            onConfirm={() => deleteMutation.mutate(provider.id)}
          >
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              disabled={isActive}
            >
              删除
            </Button>
          </Popconfirm>,
        ]}
      >
        <List.Item.Meta
          avatar={
            isActive
              ? <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
              : <span style={{ width: 20, display: 'inline-block' }}>○</span>
          }
          title={
            <Space>
              <span>{provider.name}</span>
              {isActive && <Tag color="green">激活中</Tag>}
              <Tag color={provider.type === 'ollama' ? 'blue' : 'geekblue'}>
                {provider.type === 'ollama' ? 'Ollama' : 'OpenAI 兼容'}
              </Tag>
            </Space>
          }
          description={
            <span style={{ color: '#8c8c8c', fontSize: 13 }}>
              模型: {config.model} ｜ 接口: {config.base_url}
            </span>
          }
        />
      </List.Item>
    );
  };

  return (
    <div>
      {renderProviderSwitch()}

      <Card
        title="Provider 列表"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingProvider(null);
              setModalOpen(true);
            }}
          >
            添加 Provider
          </Button>
        }
      >
        <List
          loading={isLoading}
          dataSource={providers}
          renderItem={renderProviderItem}
          locale={{ emptyText: '暂无 Provider，请点击"添加 Provider"按钮创建' }}
        />
      </Card>

      <ProviderFormModal
        open={modalOpen}
        provider={editingProvider}
        onClose={() => {
          setModalOpen(false);
          setEditingProvider(null);
        }}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['ai-providers'] });
          setModalOpen(false);
          setEditingProvider(null);
        }}
      />
    </div>
  );
};

export default AIProviders;