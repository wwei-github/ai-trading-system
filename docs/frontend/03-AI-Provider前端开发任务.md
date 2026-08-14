# 03 AI Provider 前端开发任务

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 日期 | 2026-08-14 |
| 前置文档 | [03-AI模型多Provider配置方案.md](../backend/03-AI模型多Provider配置方案.md) |
| 涉及文件 | `frontend/src/pages/system/`、`frontend/src/api/`、`frontend/src/types/`、`frontend/src/pages/ai/` |

---

## 目录

1. [任务概览](#1-任务概览)
2. [P1：类型定义与 API 封装](#2-p1类型定义与-api-封装)
3. [P1：AI Provider 管理页面（系统设置）](#3-p1ai-provider-管理页面系统设置)
4. [P1：AI 对话页 Provider 切换](#4-p1ai-对话页-provider-切换)
5. [P2：Ollama 模型获取组件](#5-p2ollama-模型获取组件)
6. [P3：收尾验证](#6-p3收尾验证)
7. [验收标准](#7-验收标准)

---

## 1. 任务概览

### 1.1 开发目标

在系统设置页面新增"AI Provider"Tab，提供以下功能：
- **查看**：展示所有已配置的 Provider 列表，标注当前激活的 Provider
- **添加**：支持添加 OpenAI 兼容接口（需 API Key）和 Ollama 本地模型
- **删除**：删除非激活的 Provider（删除按钮在激活项上禁用）
- **切换**：一键切换当前激活的 Provider
- **Ollama 模型获取**：测试连接 Ollama 并获取可用模型列表供选择

在 AI 对话页面顶部显示当前使用的 Provider 名称，支持下拉快速切换。

### 1.2 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| 新增 | `frontend/src/types/ai-provider.ts` | Provider 相关 TypeScript 类型定义 |
| 修改 | `frontend/src/types/index.ts` | 导出新类型 |
| 新增 | `frontend/src/api/ai-provider.ts` | Provider 管理 API 封装 |
| 修改 | `frontend/src/api/index.ts` | 导出新 API 模块 |
| 新增 | `frontend/src/pages/system/AIProviders.tsx` | AI Provider 管理页面 |
| 修改 | `frontend/src/pages/system/index.tsx` | 注册 AI Provider Tab |
| 修改 | `frontend/src/pages/ai/index.tsx` | AI 对话页顶部添加 Provider 切换 |

### 1.3 依赖关系

```
types/ai-provider.ts              # 独立，无依赖
api/ai-provider.ts                # 依赖: types/ai-provider.ts, request.ts
pages/system/AIProviders.tsx      # 依赖: api/ai-provider.ts, types/ai-provider.ts
pages/system/index.tsx            # 依赖: AIProviders.tsx（注册 Tab）
pages/ai/index.tsx                # 依赖: api/ai-provider.ts
```

---

## 2. P1：类型定义与 API 封装

### 2.1 类型定义

**新增文件：** [frontend/src/types/ai-provider.ts](file:///Users/wangwei/Documents/个人项目/ai-trading-system/frontend/src/types/ai-provider.ts)

```typescript
/** Provider 类型枚举 */
export type ProviderType = 'openai_compatible' | 'ollama';

/** Provider 配置（通用） */
export interface ProviderConfig {
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
  api_key?: string;           // 仅 openai_compatible 类型有
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
```

**修改 [types/index.ts](file:///Users/wangwei/Documents/个人项目/ai-trading-system/frontend/src/types/index.ts)：**

```typescript
export * from './ai-provider';
```

### 2.2 API 封装

**新增文件：** [frontend/src/api/ai-provider.ts](file:///Users/wangwei/Documents/个人项目/ai-trading-system/frontend/src/api/ai-provider.ts)

```typescript
import request from './request';
import type {
  ProviderListResponse,
  AIProvider,
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
```

**修改 [api/index.ts](file:///Users/wangwei/Documents/个人项目/ai-trading-system/frontend/src/api/index.ts)：**

```typescript
export { aiProviderApi } from './ai-provider';
```

**验收：**
- [ ] 类型定义完整，`tsc --noEmit` 无类型错误
- [ ] API 函数签名与后端接口一致

---

## 3. P1：AI Provider 管理页面（系统设置）

### 3.1 页面布局

在系统设置 Tab 中新增"AI Provider"页签，包含以下内容：

```
┌─ AI Provider 管理 ──────────────────────────────────────────────────┐
│                                                                      │
│  当前使用的 Provider: [OpenAI GPT-4o         ▼]                      │
│                                                                      │
│  ┌─── Provider 列表 ──────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  ● OpenAI GPT-4o                                   激活中       │  │
│  │    模型: gpt-4o-mini ｜ 接口: api.openai.com/v1                 │  │
│  │                                              [编辑] [删除]       │  │
│  │  ─────────────────────────────────────────────────────────────── │  │
│  │  ○ Ollama 本地                                                  │  │
│  │    模型: qwen3.5:7b ｜ 接口: ollama:11434                       │  │
│  │                                              [编辑] [删除]       │  │
│  │                                                                  │  │
│  │  [+ 添加 Provider]                                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 组件结构

**新增文件：** [frontend/src/pages/system/AIProviders.tsx](file:///Users/wangwei/Documents/个人项目/ai-trading-system/frontend/src/pages/system/AIProviders.tsx)

```typescript
// AIProviders.tsx 主组件结构

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card, Button, List, Tag, Space, Select, message, Modal, Popconfirm,
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

  // 获取 Provider 列表
  const { data, isLoading } = useQuery<ProviderListResponse>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProviderApi.getProviders(),
  });

  const providers = data?.providers || [];
  const activeProviderId = data?.active_provider_id;

  // 切换 Provider
  const activateMutation = useMutation({
    mutationFn: (id: string) => aiProviderApi.activateProvider(id),
    onSuccess: () => {
      message.success('Provider 切换成功');
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] });
    },
  });

  // 删除 Provider
  const deleteMutation = useMutation({
    mutationFn: (id: string) => aiProviderApi.deleteProvider(id),
    onSuccess: () => {
      message.success('Provider 已删除');
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] });
    },
  });

  // 顶部切换 Select
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

  // Provider 列表项
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
              {provider.type === 'openai_compatible' && ' ｜ API Key: ****'}
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
```

### 3.3 添加/编辑弹窗

**新增文件：** [frontend/src/pages/system/ProviderFormModal.tsx](file:///Users/wangwei/Documents/个人项目/ai-trading-system/frontend/src/pages/system/ProviderFormModal.tsx)

```typescript
// ProviderFormModal.tsx 组件

import { useState, useEffect } from 'react';
import {
  Modal, Form, Input, Select, Slider, InputNumber, Button, message, Space,
} from 'antd';
import { aiProviderApi } from '@/api/ai-provider';
import type { AIProvider, ProviderType, OllamaModel } from '@/types';

interface Props {
  open: boolean;
  provider: AIProvider | null;  // null=添加模式
  onClose: () => void;
  onSuccess: () => void;
}

const PROVIDER_TYPES: { value: ProviderType; label: string }[] = [
  { value: 'openai_compatible', label: 'OpenAI 兼容接口' },
  { value: 'ollama', label: 'Ollama 本地模型' },
];

const DEFAULT_CONFIG = {
  openai_compatible: {
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o-mini',
    temperature: 0.7,
    max_tokens: 2000,
  },
  ollama: {
    base_url: 'http://ollama:11434',
    model: 'qwen3.5:7b',
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

  // 打开时初始化表单
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

  // 切换类型时自动填充默认值
  const handleTypeChange = (value: ProviderType) => {
    setType(value);
    form.setFieldsValue(DEFAULT_CONFIG[value]);
    setOllamaModels([]);
  };

  // 获取 Ollama 模型列表
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
        message.info('未获取到可用模型');
      }
    } catch (e: any) {
      message.error('获取模型列表失败: ' + (e.message || '连接失败'));
    } finally {
      setFetching(false);
    }
  };

  // 提交
  const handleSubmit = async () => {
    const values = await form.validateFields();
    const payload = {
      type: type,
      name: values.name,
      config: {
        base_url: values.base_url,
        model: values.model,
        temperature: values.temperature ?? 0.7,
        max_tokens: values.max_tokens ?? (type === 'ollama' ? 4096 : 2000),
        ...(type === 'openai_compatible' ? { api_key: values.api_key } : {}),
      },
    };

    try {
      await aiProviderApi.addProvider(payload);
      message.success(isEdit ? '更新成功' : '添加成功');
      onSuccess();
    } catch (e: any) {
      message.error('操作失败: ' + (e.message || '未知错误'));
    }
  };

  return (
    <Modal
      title={isEdit ? '编辑 Provider' : '添加 Provider'}
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      width={560}
      destroyOnClose
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

        {type === 'openai_compatible' && (
          <>
            <Form.Item
              label="API Key"
              name="api_key"
              rules={isEdit ? [] : [{ required: true, message: '请输入 API Key' }]}
              extra={isEdit ? '留空则不修改已有 Key' : undefined}
            >
              <Input.Password
                placeholder={isEdit ? '留空不修改' : 'sk-...'}
                autoComplete="off"
              />
            </Form.Item>
          </>
        )}

        <Form.Item
          label="接口地址"
          name="base_url"
          rules={[{ required: true, message: '请输入接口地址' }]}
        >
          <Input placeholder={type === 'ollama' ? 'http://ollama:11434' : 'https://api.openai.com/v1'} />
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
```

### 3.4 注册到系统设置 Tab

**修改 [pages/system/index.tsx](file:///Users/wangwei/Documents/个人项目/ai-trading-system/frontend/src/pages/system/index.tsx)：**

```typescript
// 在顶部引入
import AIProviders from './AIProviders';

// 在 tabItems 中新增
const tabItems = useMemo(
  () => [
    { key: 'users', label: '用户管理', children: <UsersTab /> },
    { key: 'ai-providers', label: 'AI Provider', children: <AIProviders /> },  // 新增
    { key: 'config', label: '系统配置', children: <ConfigTab /> },
    { key: 'notifications', label: '通知设置', children: <NotificationsTab /> },
    { key: 'audit', label: '操作审计', children: <AuditTab /> },
  ],
  [],
);
```

**验收：**
- [ ] Tab 正常显示，Provider 列表正确渲染
- [ ] 添加弹窗类型切换正常（OpenAI 显示 API Key 字段，Ollama 显示"获取模型列表"按钮）
- [ ] 删除按钮在激活的 Provider 上禁用
- [ ] 切换 Select 改变后即时生效
- [ ] 无 Provider 时显示空状态提示

---

## 4. P1：AI 对话页 Provider 切换

### 4.1 页面顶部组件

**修改 [pages/ai/index.tsx](file:///Users/wangwei/Documents/个人项目/ai-trading-system/frontend/src/pages/ai/index.tsx)：**

在 AI 对话页面顶部添加 Provider 切换下拉框，位于标题行：

```tsx
// 在页面组件内添加
import { aiProviderApi } from '@/api/ai-provider';
import { useQuery } from '@tanstack/react-query';

// 在页面组件内
const { data: providerData } = useQuery({
  queryKey: ['ai-providers'],
  queryFn: () => aiProviderApi.getProviders(),
  refetchInterval: 60000,  // 每分钟刷新一次
});

const activeProvider = providerData?.providers?.find(
  (p) => p.id === providerData.active_provider_id,
);

// 在页面标题区域添加 Provider 指示器
<div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
  <span style={{ fontSize: 13, color: '#8c8c8c' }}>
    当前使用:
  </span>
  <Select
    value={providerData?.active_provider_id}
    style={{ width: 200 }}
    onChange={(id) => aiProviderApi.activateProvider(id).then(() => {
      message.success('Provider 已切换');
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] });
    })}
    options={providerData?.providers?.map((p) => ({
      value: p.id,
      label: (
        <Space>
          {p.name}
          <Tag
            color={p.type === 'ollama' ? 'blue' : 'geekblue'}
            style={{ fontSize: 10, lineHeight: '16px' }}
          >
            {p.type === 'ollama' ? '本地' : '云端'}
          </Tag>
        </Space>
      ),
    })) || []}
  />
</div>
```

### 4.2 设计参考

```
┌─ AI 助手 ─────────────────────────────────────────────────┐
│                                                             │
│  当前使用: [OpenAI GPT-4o        ▼]   [云端]                │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 用户: 帮我分析 BTC 走势                               │   │
│  │ 助手: 根据当前技术指标...                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  [输入消息...]                                    [发送]     │
└─────────────────────────────────────────────────────────────┘
```

**验收：**
- [ ] 页面顶部显示当前 Provider 名称和类型标签
- [ ] 下拉切换 Provider 即时生效
- [ ] 切换后发送新消息使用新 Provider

---

## 5. P2：Ollama 模型获取组件

### 5.1 功能说明

该功能已集成在 [ProviderFormModal.tsx](#33-添加编辑弹窗) 中，当类型选择 `ollama` 时，模型字段旁显示"获取模型列表"按钮。

**交互流程：**

```
用户点击"获取模型列表"
  → 调用 POST /api/v1/ai/providers/ollama/models
  → 后端请求 Ollama GET /api/tags
  → 返回 [{ name, size, modified_at }]
  → 前端渲染为 Select 下拉选项
  → 用户选择模型
```

### 5.2 错误处理

| 场景 | 前端提示 |
|------|----------|
| Ollama 服务未启动 | 弹窗提示"连接 Ollama 失败"，建议"请检查 Ollama 服务是否已启动" |
| 接口地址填错 | 弹窗提示"无法连接到该地址，请确认接口地址正确" |
| 无可用模型 | 提示"未获取到可用模型，请先在 Ollama 中拉取模型" |
| 网络超时 | 提示"连接超时，请检查网络和地址是否正确" |

**验收：**
- [ ] 点击"获取模型列表"能正确获取并展示模型
- [ ] 选择模型后，表单模型字段自动填充
- [ ] 连接失败时给出友好提示

---

## 6. P3：收尾验证

### 6.1 编译检查

```bash
cd frontend
npx tsc --noEmit    # 确认无类型错误
npx vite build       # 确认构建成功
```

### 6.2 功能回归

- [ ] 系统设置页原有 Tab（用户管理、系统配置、通知设置、审计）不受影响
- [ ] AI 对话页原有功能（聊天、流式、信号、报告）不受影响
- [ ] 切换 Provider 后，新对话使用新 Provider

---

## 7. 验收标准

### 7.1 功能验收

| 编号 | 验收项 | 预期结果 |
|------|--------|----------|
| F-01 | 系统设置页显示"AI Provider"Tab | Tab 正常渲染，内容正确 |
| F-02 | Provider 列表展示 | 显示所有 Provider 名称、类型、模型、接口地址 |
| F-03 | 激活状态标识 | 当前激活的 Provider 显示绿色"激活中"标签 |
| F-04 | 添加 OpenAI 兼容 Provider | 表单填写完整，保存成功，列表更新 |
| F-05 | 添加 Ollama Provider | 无需 API Key，保存成功，列表更新 |
| F-06 | 获取 Ollama 模型列表 | 点击后下拉列表显示可用模型 |
| F-07 | 切换 Provider | 顶部 Select 切换后即时生效 |
| F-08 | 删除 Provider | 非激活的删除成功，激活的按钮禁用 |
| F-09 | AI 对话页显示当前 Provider | 页面顶部正确显示 Provider 名称和类型 |

### 7.2 交互验收

| 编号 | 验收项 | 预期结果 |
|------|--------|----------|
| U-01 | 添加弹窗切换类型 | 表单字段动态切换（API Key 显隐） |
| U-02 | 空状态展示 | 无 Provider 时显示提示文字 |
| U-03 | 操作反馈 | 添加/删除/切换均有 message 提示 |
| U-04 | 删除确认 | 弹出 Popconfirm 确认对话框 |
| U-05 | Ollama 类型默认值 | 默认接口地址为 `http://ollama:11434`，模型为 `qwen3.5:7b` |

### 7.3 兼容性验收

| 编号 | 验收项 | 预期结果 |
|------|--------|----------|
| C-01 | 原有系统设置 Tab 正常 | 用户管理、配置、通知、审计 Tab 功能不受影响 |
| C-02 | 原有 AI 对话功能正常 | 聊天、流式、信号、报告功能正常 |
| C-03 | 无 Provider 时 AI 对话页 | 顶部显示"未配置 Provider"，聊天返回降级提示 |

---

> 本文档为前端开发任务清单，按优先级（P1→P3）排列。建议先完成后端 P0 任务（API 就绪）后再进行前端开发，或在开发过程中使用 mock 数据并行推进。