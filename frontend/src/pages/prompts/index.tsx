import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card, Tabs, Table, Button, Space, Tag, Typography, Modal, Form, Input, Select, Switch, message, Popconfirm, Alert,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, CopyOutlined,
} from '@ant-design/icons';
import { promptTemplateApi } from '@/api/ai-backtest';
import type {
  PromptTemplate,
  PromptTemplateListItem,
  PromptTemplateCreateRequest,
  PromptTemplateUpdateRequest,
} from '@/types/ai-backtest';
import dayjs from 'dayjs';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

// 后端仅支持 3 类(merge_optimize 未实现)
const CATEGORY_OPTIONS = [
  { value: 'initial_analysis', label: '初始化分析模板' },
  { value: 'backtest_precheck', label: '回测预筛模板' },
  { value: 'deep_analysis', label: '深度分析模板' },
] as const;

const CATEGORY_TAB_MAP: Record<string, string> = {
  initial_analysis: '初始化分析模板',
  backtest_precheck: '回测预筛模板',
  deep_analysis: '深度分析模板',
};

type PromptCategory = PromptTemplate['category'];

const PromptsPage = () => {
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<PromptCategory>('initial_analysis');
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [currentTemplate, setCurrentTemplate] = useState<PromptTemplate | null>(null);
  const [viewOpen, setViewOpen] = useState(false);
  const [viewTemplate, setViewTemplate] = useState<PromptTemplate | null>(null);
  const [form] = Form.useForm();

  // 列表查询(返回 { items, total })
  const { data: resp, isLoading } = useQuery({
    queryKey: ['prompt-templates', activeCategory],
    queryFn: () => promptTemplateApi.list({ category: activeCategory }),
    enabled: !!activeCategory,
  });

  const templates: PromptTemplateListItem[] = resp?.data?.items ?? [];

  const createMutation = useMutation({
    mutationFn: (data: PromptTemplateCreateRequest) => promptTemplateApi.create(data),
    onSuccess: () => {
      message.success('创建模板成功');
      queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
      setModalOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: PromptTemplateUpdateRequest }) =>
      promptTemplateApi.update(id, data),
    onSuccess: () => {
      message.success('更新模板成功');
      queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
      setModalOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => promptTemplateApi.remove(id),
    onSuccess: () => {
      message.success('删除模板成功');
      queryClient.invalidateQueries({ queryKey: ['prompt-templates'] });
    },
  });

  // 详情查询(查看时拉取完整 content)
  const viewMutation = useMutation({
    mutationFn: (id: string) => promptTemplateApi.get(id),
    onSuccess: (res) => {
      setViewTemplate(res.data);
      setViewOpen(true);
    },
  });

  // 打开弹窗后再回填表单，确保 Form 实例已挂载
  useEffect(() => {
    if (!modalOpen) return;
    if (modalMode === 'edit' && currentTemplate) {
      form.setFieldsValue({
        name: currentTemplate.name,
        category: currentTemplate.category,
        is_active: currentTemplate.is_active,
        content: currentTemplate.content,
      });
    } else {
      form.resetFields();
      form.setFieldsValue({ category: activeCategory, is_active: true });
    }
  }, [modalOpen, modalMode, currentTemplate, activeCategory, form]);

  const openCreate = () => {
    setCurrentTemplate(null);
    setModalMode('create');
    setModalOpen(true);
  };

  const openEdit = (record: PromptTemplateListItem) => {
    // 编辑前先拉取详情(列表项不含 content)
    promptTemplateApi.get(record.id).then((res) => {
      setCurrentTemplate(res.data);
      setModalMode('edit');
      setModalOpen(true);
    });
  };

  const openView = (record: PromptTemplateListItem) => {
    viewMutation.mutate(record.id);
  };

  const handleCopy = (record: PromptTemplateListItem) => {
    // 复制需要先拉取详情
    promptTemplateApi.get(record.id).then((res) => {
      createMutation.mutate({
        name: `${res.data.name} (副本)`,
        category: res.data.category,
        content: res.data.content,
        is_active: true,
      });
    });
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (modalMode === 'create') {
        await createMutation.mutateAsync({
          name: values.name,
          category: values.category,
          content: values.content,
          is_active: values.is_active ?? true,
        });
      } else if (currentTemplate) {
        await updateMutation.mutateAsync({
          id: currentTemplate.id,
          data: {
            name: values.name,
            content: values.content,
            is_active: values.is_active,
          },
        });
      }
    } catch {
      // 校验失败，保留弹窗
    }
  };

  const columns = useMemo(
    () => [
      {
        title: '模板名称',
        dataIndex: 'name',
        key: 'name',
        width: 220,
        render: (v: string) => <Text strong>{v}</Text>,
      },
      {
        title: '状态',
        dataIndex: 'is_active',
        key: 'is_active',
        width: 90,
        render: (v: boolean) =>
          v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>,
      },
      {
        title: '版本',
        dataIndex: 'version',
        key: 'version',
        width: 80,
        render: (v: number) => <Tag color="blue">v{v}</Tag>,
      },
      {
        title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 170,
        render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
      },
      {
        title: '更新时间',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 170,
        render: (v: string | null) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-'),
      },
      {
        title: '操作',
        key: 'actions',
        width: 280,
        render: (_: unknown, record: PromptTemplateListItem) => (
          <Space size="small">
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => openView(record)}>
              查看
            </Button>
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEdit(record)}
            >
              编辑
            </Button>
            <Button
              type="link"
              size="small"
              icon={<CopyOutlined />}
              loading={createMutation.isPending}
              onClick={() => handleCopy(record)}
            >
              复制
            </Button>
            <Popconfirm
              title="确认删除该模板？"
              description="删除后不可恢复"
              okText="删除"
              okButtonProps={{ danger: true }}
              cancelText="取消"
              onConfirm={() => deleteMutation.mutateAsync(record.id)}
            >
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [createMutation.isPending, deleteMutation],
  );

  const tabItems = CATEGORY_OPTIONS.map((opt) => ({
    key: opt.value,
    label: opt.label,
    children: (
      <Table<PromptTemplateListItem>
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={templates}
        scroll={{ x: 1000 }}
        pagination={{
          pageSize: 10,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
        }}
        locale={{ emptyText: '该分类暂无模板' }}
      />
    ),
  }));

  return (
    <div style={{ padding: 24 }}>
      <Card>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Prompt 模板说明"
          description="模板用于 AI 回测各阶段,支持 {变量名} 占位符。系统分类仅 3 种: 初始化分析 / 回测预筛 / 深度分析。"
        />
        <Tabs
          activeKey={activeCategory}
          onChange={(k) => setActiveCategory(k as PromptCategory)}
          items={tabItems}
          tabBarExtraContent={
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新建模板
            </Button>
          }
        />
      </Card>

      {/* 新建/编辑 弹窗 */}
      <Modal
        title={modalMode === 'create' ? '新建模板' : '编辑模板'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={720}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="模板名称"
            name="name"
            rules={[{ required: true, message: '请输入模板名称' }]}
          >
            <Input placeholder="如：趋势分析-Prompt" maxLength={200} />
          </Form.Item>

          <Form.Item
            label="模板分类"
            name="category"
            rules={[{ required: true, message: '请选择模板分类' }]}
          >
            <Select placeholder="请选择分类" disabled={modalMode === 'edit'}>
              {CATEGORY_OPTIONS.map((o) => (
                <Select.Option key={o.value} value={o.value}>
                  {o.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="是否启用"
            name="is_active"
            valuePropName="checked"
            tooltip="停用的模板不会被回测使用"
          >
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>

          <Form.Item
            label="模板内容"
            name="content"
            rules={[{ required: true, message: '请输入模板内容' }]}
            extra="支持使用 {变量名} 占位符，运行时自动替换"
          >
            <TextArea
              rows={12}
              placeholder="请输入 Prompt 模板内容..."
              style={{ fontFamily: 'monospace', fontSize: 13 }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 只读查看 弹窗 */}
      <Modal
        title="模板详情"
        open={viewOpen}
        onCancel={() => setViewOpen(false)}
        footer={<Button onClick={() => setViewOpen(false)}>关闭</Button>}
        width={720}
        loading={viewMutation.isPending}
      >
        {viewTemplate && (
          <div>
            <Paragraph style={{ marginBottom: 8 }}>
              <Text type="secondary">名称：</Text>
              <Text strong>{viewTemplate.name}</Text>
            </Paragraph>
            <Paragraph style={{ marginBottom: 8 }}>
              <Text type="secondary">分类：</Text>
              <Tag color="blue">{CATEGORY_TAB_MAP[viewTemplate.category] || viewTemplate.category}</Tag>
              {viewTemplate.is_active ? (
                <Tag color="green">启用</Tag>
              ) : (
                <Tag>停用</Tag>
              )}
              <Tag color="blue">v{viewTemplate.version}</Tag>
            </Paragraph>
            <div style={{ marginBottom: 8 }}>
              <Text type="secondary">内容：</Text>
            </div>
            <pre
              style={{
                background: '#f5f5f5',
                padding: 16,
                borderRadius: 6,
                maxHeight: 400,
                overflow: 'auto',
                fontFamily: 'monospace',
                fontSize: 13,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                margin: 0,
              }}
            >
              {viewTemplate.content}
            </pre>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default PromptsPage;
