import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tooltip,
  message,
  Tag,
  Modal,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  ApiOutlined,
  SyncOutlined,
  EditOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  PageContainer,
  SearchForm,
  CrudModal,
  StatusTag,
  ConfirmButton,
  EmptyState,
} from '@/components/Common';
import { accountApi } from '@/api/accounts';
import type {
  Account,
  AccountCreateData,
  AccountListParams,
  AccountUpdateData,
} from '@/types';
import { EXCHANGE_OPTIONS, ACCOUNT_STATUS_MAP } from '@/types/accounts';

const AccountsPage = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useState<AccountListParams>({
    page: 1,
    page_size: 10,
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [currentRecord, setCurrentRecord] = useState<Account | null>(null);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());
  const [testingIds, setTestingIds] = useState<Set<string>>(new Set());

  // ========== 查询账号列表 ==========
  // 后端返回全量数组，过滤与分页在前端完成
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['accounts', 'list'],
    queryFn: () => accountApi.getList(),
  });

  // ========== 客户端过滤 ==========
  const filteredAccounts = useMemo(() => {
    const list = data || [];
    return list.filter((acc) => {
      if (searchParams.exchange && acc.exchange !== searchParams.exchange) return false;
      if (searchParams.status && acc.status !== searchParams.status) return false;
      if (searchParams.keyword) {
        const kw = searchParams.keyword.toLowerCase();
        if (!acc.label.toLowerCase().includes(kw)) return false;
      }
      return true;
    });
  }, [data, searchParams.exchange, searchParams.status, searchParams.keyword]);

  // ========== 新增/编辑 ==========
  const createMutation = useMutation({
    mutationFn: (d: AccountCreateData) => accountApi.create(d),
    onSuccess: () => {
      message.success('创建成功');
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      setModalOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: AccountUpdateData }) =>
      accountApi.update(id, data),
    onSuccess: () => {
      message.success('修改成功');
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      setModalOpen(false);
    },
  });

  // ========== 删除 ==========
  const deleteMutation = useMutation({
    mutationFn: (id: string) => accountApi.delete(id),
    onSuccess: () => {
      message.success('删除成功');
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
    },
  });

  // ========== 连接测试 ==========
  const handleTestConnection = async (id: string) => {
    setTestingIds((prev) => new Set(prev).add(id));
    try {
      const res = await accountApi.testConnection(id);
      if (res.success) {
        const latency = res.latency_ms ? `（延迟 ${res.latency_ms}ms）` : '';
        Modal.success({
          title: '连接成功',
          content: (
            <div>
              <p>{res.message}{latency}</p>
              {res.permissions && (
                <p>
                  权限：
                  {res.permissions.map((p) => (
                    <Tag key={p} color="blue">{p}</Tag>
                  ))}
                </p>
              )}
            </div>
          ),
        });
      } else {
        Modal.error({ title: '连接失败', content: res.message });
      }
    } finally {
      setTestingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  // ========== 同步账号 ==========
  const handleSyncAccount = async (id: string) => {
    setSyncingIds((prev) => new Set(prev).add(id));
    try {
      await accountApi.syncAccount(id);
      message.success('同步成功');
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
    } finally {
      setSyncingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  // ========== 搜索条件 ==========
  const searchFields = useMemo(
    () => [
      {
        name: 'exchange',
        label: '交易所',
        placeholder: '全部',
        element: (
          <Select allowClear placeholder="请选择交易所">
            {EXCHANGE_OPTIONS.map((o) => (
              <Select.Option key={o.value} value={o.value}>
                <Space>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      background: o.color,
                      display: 'inline-block',
                    }}
                  />
                  {o.label}
                </Space>
              </Select.Option>
            ))}
          </Select>
        ),
      },
      {
        name: 'status',
        label: '状态',
        placeholder: '全部',
        element: (
          <Select allowClear placeholder="请选择状态">
            {Object.entries(ACCOUNT_STATUS_MAP).map(([k, v]) => (
              <Select.Option key={k} value={k}>{v.text}</Select.Option>
            ))}
          </Select>
        ),
      },
      {
        name: 'keyword',
        label: '关键字',
        placeholder: '搜索标签',
        element: (
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="输入关键字"
          />
        ),
      },
    ],
    [],
  );

  // ========== 表格列 ==========
  const columns = useMemo(
    () => [
      {
        title: '交易所',
        dataIndex: 'exchange',
        key: 'exchange',
        width: 140,
        render: (val: string) => {
          const opt = EXCHANGE_OPTIONS.find((o) => o.value === val);
          return (
            <Space>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 5,
                  background: opt?.color || '#ccc',
                }}
              />
              {opt?.label || val}
            </Space>
          );
        },
      },
      {
        title: '标签',
        dataIndex: 'label',
        key: 'label',
        width: 180,
        render: (v: string) => <strong>{v}</strong>,
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (v) => <StatusTag status={v} mapping={ACCOUNT_STATUS_MAP} />,
      },
      {
        title: '网络',
        dataIndex: 'is_testnet',
        key: 'is_testnet',
        width: 100,
        render: (v: boolean) =>
          v ? <Tag color="orange">测试网</Tag> : <Tag color="green">正式</Tag>,
      },
      {
        title: '权限',
        dataIndex: 'permissions',
        key: 'permissions',
        width: 180,
        render: (v?: string[]) =>
          v && v.length > 0 ? (
            <Space size={[0, 4]} wrap>
              {v.map((p) => (
                <Tag key={p} color="blue">{p}</Tag>
              ))}
            </Space>
          ) : (
            '-'
          ),
      },
      {
        title: '最后同步',
        dataIndex: 'last_sync_at',
        key: 'last_sync_at',
        width: 170,
        render: (v?: string) => v && dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
      },
      {
        title: '操作',
        key: 'actions',
        width: 280,
        fixed: 'right' as const,
        render: (_: any, record: Account) => {
          const isSyncing = syncingIds.has(record.id);
          const isTesting = testingIds.has(record.id);
          return (
            <Space size="small">
              <Tooltip title="连接测试">
                <Button
                  type="link"
                  size="small"
                  icon={<ApiOutlined />}
                  loading={isTesting}
                  onClick={() => handleTestConnection(record.id)}
                >
                  测试
                </Button>
              </Tooltip>
              <Tooltip title="同步账号">
                <Button
                  type="link"
                  size="small"
                  icon={<SyncOutlined />}
                  loading={isSyncing}
                  onClick={() => handleSyncAccount(record.id)}
                >
                  同步
                </Button>
              </Tooltip>
              <Button
                type="link"
                size="small"
                icon={<EditOutlined />}
                onClick={() => {
                  setCurrentRecord(record);
                  setModalMode('edit');
                  setModalOpen(true);
                }}
              >
                编辑
              </Button>
              <ConfirmButton
                label="删除"
                type="link"
                size="small"
                title="确认删除该交易所账号？"
                description="删除后将无法恢复相关交易记录关联"
                onConfirm={() => deleteMutation.mutateAsync(record.id)}
              />
            </Space>
          );
        },
      },
    ],
    [syncingIds, testingIds, deleteMutation],
  );

  // ========== 弹窗提交 ==========
  const handleModalSubmit = async (values: any) => {
    if (modalMode === 'create') {
      await createMutation.mutateAsync(values);
    } else if (currentRecord) {
      await updateMutation.mutateAsync({ id: currentRecord.id, data: values });
    }
  };

  return (
    <PageContainer
      breadcrumbs={[{ title: '交易所账号' }]}
      title="交易所账号管理"
      description="支持多交易所账号统一管理、API Key 连接测试与余额同步"
      extra={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setCurrentRecord(null);
            setModalMode('create');
            setModalOpen(true);
          }}
        >
          新增账号
        </Button>
      }
    >
      {/* 筛选区 */}
      <div style={{ marginBottom: 16 }}>
        <SearchForm
          fields={searchFields}
          initialValues={searchParams}
          onSearch={(values: any) => {
            setSearchParams((prev) => ({
              ...prev,
              ...values,
              page: 1,
            }));
          }}
          extraButtons={
            <Tooltip title="刷新列表">
              <Button icon={<ReloadOutlined />} onClick={() => refetch()} />
            </Tooltip>
          }
        />
      </div>

      {/* 表格 */}
      <Table<Account>
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={filteredAccounts}
        scroll={{ x: 1200 }}
        pagination={{
          current: searchParams.page,
          pageSize: searchParams.page_size,
          total: filteredAccounts.length,
          showSizeChanger: true,
          showQuickJumper: true,
          pageSizeOptions: ['10', '20', '50', '100'],
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => {
            setSearchParams((prev) => ({ ...prev, page, page_size: pageSize }));
          },
        }}
        locale={{
          emptyText: <EmptyState description="暂无账号，点击右上角新增账号" />,
        }}
      />

      {/* 新增/编辑 弹窗 */}
      <CrudModal
        open={modalOpen}
        mode={modalMode}
        entityName="交易所账号"
        initialValues={
          currentRecord
            ? {
                exchange: currentRecord.exchange,
                label: currentRecord.label,
                api_key: '',
                api_secret: '',
                passphrase: '',
              }
            : undefined
        }
        onOk={handleModalSubmit}
        onCancel={() => setModalOpen(false)}
      >
        <Form.Item
          label="交易所"
          name="exchange"
          rules={[{ required: true, message: '请选择交易所' }]}
        >
          <Select placeholder="请选择交易所">
            {EXCHANGE_OPTIONS.map((o) => (
              <Select.Option key={o.value} value={o.value}>
                <Space>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      background: o.color,
                      display: 'inline-block',
                    }}
                  />
                  {o.label}
                </Space>
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          label="标签"
          name="label"
          rules={[{ required: true, message: '请输入账号标签' }]}
        >
          <Input placeholder="如：币安-主账号-1" maxLength={50} />
        </Form.Item>

        <Form.Item
          label="API Key"
          name="api_key"
          rules={[
            {
              required: modalMode === 'create',
              message: '请输入 API Key',
            },
          ]}
          extra={modalMode === 'edit' ? '留空则不修改' : ''}
        >
          <Input.Password placeholder="请输入 API Key" />
        </Form.Item>

        <Form.Item
          label="API Secret"
          name="api_secret"
          rules={[
            {
              required: modalMode === 'create',
              message: '请输入 API Secret',
            },
          ]}
          extra={modalMode === 'edit' ? '留空则不修改' : ''}
        >
          <Input.Password placeholder="请输入 API Secret" />
        </Form.Item>

        <Form.Item label="Passphrase" name="passphrase">
          <Input.Password placeholder="部分交易所需要（如 OKX）" />
        </Form.Item>
      </CrudModal>
    </PageContainer>
  );
};

export default AccountsPage;
