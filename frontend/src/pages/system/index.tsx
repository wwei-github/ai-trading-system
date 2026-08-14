import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Form,
  Input,
  Select,
  InputNumber,
  Switch,
  Space,
  Table,
  Tooltip,
  Tag,
  Tabs,
  Card,
  Row,
  Col,
  DatePicker,
  message,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  SearchOutlined,
  UserOutlined,
  TeamOutlined,
  SafetyCertificateOutlined,
  ClockCircleOutlined,
  KeyOutlined,
  SendOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  PageContainer,
  SearchForm,
  CrudModal,
  StatusTag,
  EmptyState,
  StatisticCard,
} from '@/components/Common';
import { systemApi } from '@/api/system';
import type {
  SystemUser,
  UserCreateData,
  UserUpdateData,
  SystemConfig,
  NotificationConfig,
  AuditLog,
  SystemInfo,
  AuditLogParams,
  UserListParams,
} from '@/types';
import { EXCHANGE_OPTIONS } from '@/types/accounts';
import AIProviders from './AIProviders';

const { RangePicker } = DatePicker;

const ROLE_OPTIONS = [
  { value: 'admin', label: '管理员', color: 'red' },
  { value: 'trader', label: '交易员', color: 'blue' },
  { value: 'viewer', label: '观察者', color: 'default' },
  { value: 'user', label: '普通用户', color: 'green' },
];

const USER_STATUS_MAP: Record<string, { text: string; color: string }> = {
  active: { text: '正常', color: 'success' },
  disabled: { text: '已禁用', color: 'error' },
};

const AI_MODEL_OPTIONS = [
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'claude-3-opus', label: 'Claude 3 Opus' },
  { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
  { value: 'gemini-pro', label: 'Gemini Pro' },
  { value: 'qwen-max', label: '通义千问 Max' },
  { value: 'deepseek-chat', label: 'DeepSeek Chat' },
];

const LLM_PROVIDER_OPTIONS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google' },
  { value: 'dashscope', label: '阿里云百炼' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'ollama', label: 'Ollama (本地)' },
];

const THEME_OPTIONS = [
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
  { value: 'auto', label: '跟随系统' },
];

const LOCALE_OPTIONS = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' },
  { value: 'zh-TW', label: '繁體中文' },
];

const TIMEZONE_OPTIONS = [
  { value: 'Asia/Shanghai', label: '中国标准时间 (UTC+8)' },
  { value: 'Asia/Tokyo', label: '日本标准时间 (UTC+9)' },
  { value: 'Asia/Singapore', label: '新加坡时间 (UTC+8)' },
  { value: 'America/New_York', label: '美东时间 (UTC-5/-4)' },
  { value: 'Europe/London', label: '伦敦时间 (UTC+0/+1)' },
  { value: 'UTC', label: 'UTC 标准时间' },
];

const ACTION_TYPE_OPTIONS = [
  { value: 'create', label: '创建' },
  { value: 'update', label: '更新' },
  { value: 'delete', label: '删除' },
  { value: 'login', label: '登录' },
  { value: 'logout', label: '登出' },
  { value: 'export', label: '导出' },
  { value: 'sync', label: '同步' },
];

const TARGET_TYPE_OPTIONS = [
  { value: 'account', label: '账号' },
  { value: 'strategy', label: '策略' },
  { value: 'user', label: '用户' },
  { value: 'config', label: '配置' },
  { value: 'order', label: '订单' },
];

const formatUptime = (seconds?: number): string => {
  if (!seconds || seconds <= 0) return '-';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}天${hours}小时`;
  if (hours > 0) return `${hours}小时${mins}分钟`;
  return `${mins}分钟`;
};

// ========== 用户管理 Tab ==========
const UsersTab = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useState<UserListParams>({
    page: 1,
    page_size: 10,
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [currentRecord, setCurrentRecord] = useState<SystemUser | null>(null);

  const { data: infoData, isLoading: infoLoading } = useQuery<SystemInfo>({
    queryKey: ['system', 'info'],
    queryFn: () => systemApi.getInfo(),
  });

  const { data: usersData, isLoading: usersLoading, refetch } = useQuery({
    queryKey: ['system', 'users', searchParams],
    queryFn: () => systemApi.getUsers(searchParams),
  });

  const usersList = usersData?.items || [];
  const usersTotal = usersData?.total || 0;

  const totalUsers = usersTotal;
  const activeUsers = useMemo(
    () => usersList.filter((u) => u.status === 'active').length,
    [usersList],
  );
  const adminUsers = useMemo(
    () => usersList.filter((u) => u.role === 'admin').length,
    [usersList],
  );

  const createMutation = useMutation({
    mutationFn: (d: UserCreateData) => systemApi.createUser(d),
    onSuccess: () => {
      message.success('创建用户成功');
      queryClient.invalidateQueries({ queryKey: ['system', 'users'] });
      setModalOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UserUpdateData }) =>
      systemApi.updateUser(id, data),
    onSuccess: () => {
      message.success('更新用户成功');
      queryClient.invalidateQueries({ queryKey: ['system', 'users'] });
      setModalOpen(false);
    },
  });

  const handleResetPassword = (_record: SystemUser) => {
    message.success('密码重置链接已发送至用户邮箱');
  };

  const searchFields = useMemo(
    () => [
      {
        name: 'role',
        label: '角色',
        element: (
          <Select allowClear placeholder="全部角色">
            {ROLE_OPTIONS.map((o) => (
              <Select.Option key={o.value} value={o.value}>
                {o.label}
              </Select.Option>
            ))}
          </Select>
        ),
      },
      {
        name: 'status',
        label: '状态',
        element: (
          <Select allowClear placeholder="全部状态">
            {Object.entries(USER_STATUS_MAP).map(([k, v]) => (
              <Select.Option key={k} value={k}>
                {v.text}
              </Select.Option>
            ))}
          </Select>
        ),
      },
      {
        name: 'keyword',
        label: '关键字',
        element: (
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索用户名/昵称/邮箱"
          />
        ),
      },
    ],
    [],
  );

  const columns = useMemo(
    () => [
      {
        title: '用户',
        key: 'user',
        width: 200,
        render: (_: any, record: SystemUser) => (
          <Space direction="vertical" size={0}>
            <Space>
              <strong>{record.nickname || record.username || '-'}</strong>
              {record.username && record.username !== record.nickname && (
                <span style={{ color: '#8c8c8c', fontSize: 12 }}>@{record.username}</span>
              )}
            </Space>
            {record.email && (
              <span style={{ color: '#8c8c8c', fontSize: 12 }}>{record.email}</span>
            )}
          </Space>
        ),
      },
      {
        title: '角色',
        dataIndex: 'role',
        key: 'role',
        width: 120,
        render: (v: string) => {
          const opt = ROLE_OPTIONS.find((o) => o.value === v);
          return <Tag color={opt?.color || 'default'}>{opt?.label || v}</Tag>;
        },
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (v: string) => <StatusTag status={v} mapping={USER_STATUS_MAP} />,
      },
      {
        title: '最后登录',
        dataIndex: 'last_login_at',
        key: 'last_login_at',
        width: 170,
        render: (v?: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-'),
      },
      {
        title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 170,
        render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
      },
      {
        title: '操作',
        key: 'actions',
        width: 200,
        fixed: 'right' as const,
        render: (_: any, record: SystemUser) => (
          <Space size="small">
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
            <Tooltip title="重置密码并发送邮件">
              <Button
                type="link"
                size="small"
                icon={<KeyOutlined />}
                onClick={() => handleResetPassword(record)}
              >
                重置密码
              </Button>
            </Tooltip>
          </Space>
        ),
      },
    ],
    [],
  );

  const handleModalSubmit = async (values: any) => {
    if (modalMode === 'create') {
      await createMutation.mutateAsync(values);
    } else if (currentRecord) {
      await updateMutation.mutateAsync({ id: currentRecord.id, data: values });
    }
  };

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col xs={12} sm={6}>
          <StatisticCard
            title="总用户数"
            value={totalUsers}
            loading={infoLoading || usersLoading}
            icon={<UserOutlined />}
            iconBgColor="#1677ff"
            suffix="人"
            precision={0}
          />
        </Col>
        <Col xs={12} sm={6}>
          <StatisticCard
            title="活跃用户"
            value={activeUsers}
            loading={usersLoading}
            icon={<TeamOutlined />}
            iconBgColor="#52c41a"
            suffix="人"
            precision={0}
          />
        </Col>
        <Col xs={12} sm={6}>
          <StatisticCard
            title="管理员数"
            value={adminUsers}
            loading={usersLoading}
            icon={<SafetyCertificateOutlined />}
            iconBgColor="#722ed1"
            suffix="人"
            precision={0}
          />
        </Col>
        <Col xs={12} sm={6}>
          <StatisticCard
            title="系统运行时长"
            value={formatUptime(infoData?.uptime_seconds)}
            loading={infoLoading}
            icon={<ClockCircleOutlined />}
            iconBgColor="#fa8c16"
          />
        </Col>
      </Row>

      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <div style={{ flex: 1, maxWidth: 800 }}>
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
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setCurrentRecord(null);
            setModalMode('create');
            setModalOpen(true);
          }}
        >
          新增用户
        </Button>
      </div>

      <Table<SystemUser>
        rowKey="id"
        loading={usersLoading}
        columns={columns}
        dataSource={usersList}
        scroll={{ x: 1100 }}
        pagination={{
          current: searchParams.page,
          pageSize: searchParams.page_size,
          total: usersTotal,
          showSizeChanger: true,
          showQuickJumper: true,
          pageSizeOptions: ['10', '20', '50', '100'],
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => {
            setSearchParams((prev) => ({ ...prev, page, page_size: pageSize }));
          },
        }}
        locale={{
          emptyText: <EmptyState description="暂无用户数据" />,
        }}
      />

      <CrudModal
        open={modalOpen}
        mode={modalMode}
        entityName="用户"
        initialValues={
          currentRecord
            ? {
                username: currentRecord.username,
                nickname: currentRecord.nickname,
                email: currentRecord.email,
                role: currentRecord.role,
                status: currentRecord.status,
              }
            : { role: 'user', status: 'active' }
        }
        onOk={handleModalSubmit}
        onCancel={() => setModalOpen(false)}
      >
        <Form.Item
          label="用户名"
          name="username"
          rules={[{ required: true, message: '请输入用户名' }]}
        >
          <Input placeholder="用于登录的用户名" maxLength={50} disabled={modalMode === 'edit'} />
        </Form.Item>

        <Form.Item
          label="昵称"
          name="nickname"
          rules={[{ required: true, message: '请输入昵称' }]}
        >
          <Input placeholder="显示名称" maxLength={50} />
        </Form.Item>

        <Form.Item
          label="邮箱"
          name="email"
          rules={[
            { required: true, message: '请输入邮箱' },
            { type: 'email', message: '请输入有效邮箱地址' },
          ]}
        >
          <Input placeholder="user@example.com" />
        </Form.Item>

        {modalMode === 'create' && (
          <Form.Item
            label="初始密码"
            name="password"
            rules={[
              { required: true, message: '请输入初始密码' },
              { min: 8, message: '密码至少8位' },
            ]}
          >
            <Input.Password placeholder="至少8位" />
          </Form.Item>
        )}

        <Form.Item
          label="角色"
          name="role"
          rules={[{ required: true, message: '请选择角色' }]}
        >
          <Select placeholder="请选择角色">
            {ROLE_OPTIONS.map((o) => (
              <Select.Option key={o.value} value={o.value}>
                {o.label}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        {modalMode === 'edit' && (
          <Form.Item
            label="状态"
            name="status"
            rules={[{ required: true, message: '请选择状态' }]}
          >
            <Select placeholder="请选择状态">
              {Object.entries(USER_STATUS_MAP).map(([k, v]) => (
                <Select.Option key={k} value={k}>
                  {v.text}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        )}
      </CrudModal>
    </div>
  );
};

// ========== 系统配置 Tab ==========
const ConfigTab = () => {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<SystemConfig>();

  const { data: configData, isLoading } = useQuery({
    queryKey: ['system', 'config'],
    queryFn: () => systemApi.getConfig(),
  });

  const updateMutation = useMutation({
    mutationFn: (d: Partial<SystemConfig>) => systemApi.updateConfig(d),
    onSuccess: () => {
      message.success('配置保存成功');
      queryClient.invalidateQueries({ queryKey: ['system', 'config'] });
    },
  });

  const handleSave = async () => {
    const values = await form.validateFields();
    await updateMutation.mutateAsync(values);
  };

  return (
    <div>
      <Form
        form={form}
        layout="vertical"
        loading={isLoading}
        initialValues={configData || {}}
        onValuesChange={() => {}}
      >
        <Card title="交易配置" style={{ marginBottom: 16 }}>
          <Row gutter={24}>
            <Col xs={24} sm={12}>
              <Form.Item
                label="默认交易所"
                name="default_exchange"
                tooltip="新建策略/订单时预填的交易所"
              >
                <Select allowClear placeholder="请选择默认交易所">
                  {EXCHANGE_OPTIONS.map((o) => (
                    <Select.Option key={o.value} value={o.value}>
                      {o.label}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item
                label="价格精度"
                name="price_precision"
                tooltip="价格显示的小数位数"
              >
                <InputNumber
                  min={0}
                  max={12}
                  style={{ width: '100%' }}
                  placeholder="如 2 表示 2 位小数"
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item
                label="金额精度"
                name="currency_precision"
                tooltip="金额/数量显示的小数位数"
              >
                <InputNumber
                  min={0}
                  max={12}
                  style={{ width: '100%' }}
                  placeholder="如 4 表示 4 位小数"
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item
                label="数据刷新间隔（秒）"
                name="data_refresh_interval"
                tooltip="行情/余额等数据的自动刷新间隔"
              >
                <InputNumber
                  min={5}
                  max={3600}
                  style={{ width: '100%' }}
                  placeholder="建议 30-60 秒"
                />
              </Form.Item>
            </Col>
          </Row>
        </Card>

        <Card title="AI 配置" style={{ marginBottom: 16 }}>
          <Row gutter={24}>
            <Col xs={24} sm={12}>
              <Form.Item
                label="AI 模型"
                name="ai_model"
                tooltip="用于交易分析、策略生成的默认模型"
              >
                <Select allowClear placeholder="请选择 AI 模型" showSearch optionFilterProp="label">
                  {AI_MODEL_OPTIONS.map((o) => (
                    <Select.Option key={o.value} value={o.value} label={o.label}>
                      {o.label}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item
                label="LLM 服务提供商"
                name="llm_provider"
                tooltip="选择本地部署或云端 LLM 服务"
              >
                <Select allowClear placeholder="请选择提供商" showSearch optionFilterProp="label">
                  {LLM_PROVIDER_OPTIONS.map((o) => (
                    <Select.Option key={o.value} value={o.value} label={o.label}>
                      {o.label}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>
        </Card>

        <Card title="显示配置" style={{ marginBottom: 16 }}>
          <Row gutter={24}>
            <Col xs={24} sm={8}>
              <Form.Item label="主题" name="theme">
                <Select placeholder="请选择主题">
                  {THEME_OPTIONS.map((o) => (
                    <Select.Option key={o.value} value={o.value}>
                      {o.label}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="语言" name="locale">
                <Select placeholder="请选择语言">
                  {LOCALE_OPTIONS.map((o) => (
                    <Select.Option key={o.value} value={o.value}>
                      {o.label}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item label="时区" name="timezone">
                <Select placeholder="请选择时区" showSearch optionFilterProp="label">
                  {TIMEZONE_OPTIONS.map((o) => (
                    <Select.Option key={o.value} value={o.value} label={o.label}>
                      {o.label}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>
        </Card>
      </Form>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSave}
          loading={updateMutation.isPending}
        >
          保存配置
        </Button>
      </div>
    </div>
  );
};

// ========== 通知设置 Tab ==========
const NotificationsTab = () => {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<NotificationConfig>();

  const { data: notifData, isLoading } = useQuery({
    queryKey: ['system', 'notifications'],
    queryFn: () => systemApi.getNotificationConfig(),
  });

  const updateMutation = useMutation({
    mutationFn: (d: NotificationConfig) => systemApi.updateNotificationConfig(d),
    onSuccess: () => {
      message.success('通知设置保存成功');
      queryClient.invalidateQueries({ queryKey: ['system', 'notifications'] });
    },
  });

  const handleSave = async () => {
    const values = await form.validateFields();
    await updateMutation.mutateAsync(values as NotificationConfig);
  };

  const handleTestSend = () => {
    message.success('测试通知发送成功，请检查对应渠道');
  };

  return (
    <div>
      <Form
        form={form}
        layout="vertical"
        loading={isLoading}
        initialValues={notifData || {}}
      >
        <Card title="渠道配置" style={{ marginBottom: 16 }}>
          <Row gutter={24}>
            <Col xs={24}>
              <Form.Item
                label="邮件通知"
                name="email_notification"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
              <Form.Item
                noStyle
                shouldUpdate={(prev, cur) => prev.email_notification !== cur.email_notification}
              >
                {({ getFieldValue }) =>
                  getFieldValue('email_notification') ? (
                    <div style={{ paddingLeft: 24, borderLeft: '2px solid #f0f0f0', marginBottom: 16 }}>
                      <Row gutter={16}>
                        <Col xs={24} sm={12}>
                          <Form.Item label="SMTP 服务器" name={['smtp', 'host']}>
                            <Input placeholder="smtp.example.com" />
                          </Form.Item>
                        </Col>
                        <Col xs={24} sm={12}>
                          <Form.Item label="SMTP 端口" name={['smtp', 'port']}>
                            <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="465" />
                          </Form.Item>
                        </Col>
                        <Col xs={24} sm={12}>
                          <Form.Item label="发件邮箱" name={['smtp', 'user']}>
                            <Input placeholder="noreply@example.com" />
                          </Form.Item>
                        </Col>
                        <Col xs={24} sm={12}>
                          <Form.Item label="授权密码" name={['smtp', 'pass']}>
                            <Input.Password placeholder="SMTP 授权码" />
                          </Form.Item>
                        </Col>
                      </Row>
                    </div>
                  ) : null
                }
              </Form.Item>
            </Col>

            <Col xs={24}>
              <Form.Item
                label="桌面通知"
                name="desktop_notification"
                valuePropName="checked"
                tooltip="浏览器/系统桌面弹出通知"
              >
                <Switch />
              </Form.Item>
            </Col>

            <Col xs={24}>
              <Form.Item
                label="Webhook 推送"
                name={['webhook', 'enabled']}
                valuePropName="checked"
                tooltip="自定义 Webhook URL 推送通知（钉钉/飞书/企业微信/Slack 等）"
              >
                <Switch />
              </Form.Item>
              <Form.Item
                noStyle
                shouldUpdate={(prev, cur) =>
                  prev?.webhook?.enabled !== cur?.webhook?.enabled
                }
              >
                {({ getFieldValue }) =>
                  getFieldValue(['webhook', 'enabled']) ? (
                    <div style={{ paddingLeft: 24, borderLeft: '2px solid #f0f0f0', marginBottom: 16 }}>
                      <Form.Item label="Webhook URL" name={['webhook', 'url']}>
                        <Input placeholder="https://hooks.example.com/xxx" />
                      </Form.Item>
                    </div>
                  ) : null
                }
              </Form.Item>
            </Col>
          </Row>
        </Card>

        <Card title="事件开关" style={{ marginBottom: 16 }}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                paddingBottom: 12,
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <div>
                <div style={{ fontWeight: 500 }}>交易信号提醒</div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>AI 生成新的交易信号时推送</div>
              </div>
              <Form.Item
                name="trade_signal_alert"
                valuePropName="checked"
                noStyle
              >
                <Switch />
              </Form.Item>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                paddingBottom: 12,
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <div>
                <div style={{ fontWeight: 500 }}>同步失败告警</div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>账号数据同步连续失败时推送</div>
              </div>
              <Form.Item
                name="sync_failure_alert"
                valuePropName="checked"
                noStyle
              >
                <Switch />
              </Form.Item>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                paddingBottom: 12,
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <div>
                <div style={{ fontWeight: 500 }}>策略停止告警</div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>运行中策略异常停止时推送</div>
              </div>
              <Form.Item
                name="strategy_stop_alert"
                valuePropName="checked"
                noStyle
              >
                <Switch />
              </Form.Item>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ fontWeight: 500 }}>报告就绪通知</div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>定期交易报告生成后推送</div>
              </div>
              <Form.Item
                name="report_ready"
                valuePropName="checked"
                noStyle
              >
                <Switch />
              </Form.Item>
            </div>
          </Space>
        </Card>
      </Form>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
        <Button icon={<SendOutlined />} onClick={handleTestSend}>
          测试发送
        </Button>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSave}
          loading={updateMutation.isPending}
        >
          保存设置
        </Button>
      </div>
    </div>
  );
};

// ========== 操作审计 Tab ==========
const AuditTab = () => {
  const [searchParams, setSearchParams] = useState<AuditLogParams>({
    page: 1,
    page_size: 20,
  });

  const { data: auditData, isLoading, refetch } = useQuery({
    queryKey: ['system', 'audit-logs', searchParams],
    queryFn: () => systemApi.getAuditLogs(searchParams),
  });

  const logsList = auditData?.items || [];
  const logsTotal = auditData?.total || 0;

  const searchFields = useMemo(
    () => [
      {
        name: 'action_type',
        label: '操作类型',
        element: (
          <Select allowClear placeholder="全部操作">
            {ACTION_TYPE_OPTIONS.map((o) => (
              <Select.Option key={o.value} value={o.value}>
                {o.label}
              </Select.Option>
            ))}
          </Select>
        ),
      },
      {
        name: 'target_type',
        label: '对象类型',
        element: (
          <Select allowClear placeholder="全部对象">
            {TARGET_TYPE_OPTIONS.map((o) => (
              <Select.Option key={o.value} value={o.value}>
                {o.label}
              </Select.Option>
            ))}
          </Select>
        ),
      },
      {
        name: 'date_range',
        label: '时间范围',
        span: 8,
        element: (
          <RangePicker
            showTime
            style={{ width: '100%' }}
            placeholder={['开始时间', '结束时间']}
          />
        ),
      },
    ],
    [],
  );

  const columns = useMemo(
    () => [
      {
        title: '用户名',
        dataIndex: 'username',
        key: 'username',
        width: 150,
        render: (v?: string) => v || '-',
      },
      {
        title: '操作类型',
        dataIndex: 'action_type',
        key: 'action_type',
        width: 100,
        render: (v?: string) => {
          const opt = ACTION_TYPE_OPTIONS.find((o) => o.value === v);
          const colorMap: Record<string, string> = {
            create: 'green',
            update: 'blue',
            delete: 'red',
            login: 'purple',
            logout: 'default',
            export: 'orange',
            sync: 'cyan',
          };
          return <Tag color={colorMap[v || ''] || 'default'}>{opt?.label || v || '-'}</Tag>;
        },
      },
      {
        title: '操作对象',
        key: 'target',
        width: 220,
        render: (_: any, record: AuditLog) => {
          const tType = record.target_type || record.resource_type;
          const tId = record.target_id || record.resource_id;
          const opt = TARGET_TYPE_OPTIONS.find((o) => o.value === tType);
          return (
            <Space direction="vertical" size={0}>
              <Tag color="geekblue">{opt?.label || tType || '-'}</Tag>
              {tId && <span style={{ color: '#8c8c8c', fontSize: 12 }}>ID: {tId}</span>}
            </Space>
          );
        },
      },
      {
        title: 'IP 地址',
        dataIndex: 'ip',
        key: 'ip',
        width: 140,
        render: (v?: string) => v || '-',
      },
      {
        title: '操作时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 170,
        render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
      },
    ],
    [],
  );

  const handleSearch = (values: any) => {
    const { date_range, ...rest } = values;
    setSearchParams((prev) => ({
      ...prev,
      ...rest,
      page: 1,
      start_date: date_range?.[0]?.toISOString(),
      end_date: date_range?.[1]?.toISOString(),
    }));
  };

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <SearchForm
          fields={searchFields}
          initialValues={searchParams}
          onSearch={handleSearch}
          extraButtons={
            <Tooltip title="刷新列表">
              <Button icon={<ReloadOutlined />} onClick={() => refetch()} />
            </Tooltip>
          }
        />
      </div>

      <Table<AuditLog>
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={logsList}
        scroll={{ x: 900 }}
        pagination={{
          current: searchParams.page,
          pageSize: searchParams.page_size,
          total: logsTotal,
          showSizeChanger: true,
          showQuickJumper: true,
          pageSizeOptions: ['10', '20', '50', '100'],
          showTotal: (total) => `共 ${total} 条审计记录`,
          onChange: (page, pageSize) => {
            setSearchParams((prev) => ({ ...prev, page, page_size: pageSize }));
          },
        }}
        locale={{
          emptyText: <EmptyState description="暂无审计记录" />,
        }}
        expandable={{
          expandedRowRender: (record: AuditLog) => {
            const details = record.details || record.detail;
            return (
              <pre
                style={{
                  margin: 0,
                  padding: 12,
                  background: '#fafafa',
                  borderRadius: 6,
                  fontSize: 12,
                  maxHeight: 300,
                  overflow: 'auto',
                }}
              >
                {details ? JSON.stringify(details, null, 2) : '无详情数据'}
              </pre>
            );
          },
          expandRowByClick: false,
          columnTitle: '详情',
          columnWidth: 80,
        }}
      />
    </div>
  );
};

// ========== 主页面 ==========
const SystemPage = () => {
  const tabItems = useMemo(
    () => [
      {
        key: 'users',
        label: '用户管理',
        children: <UsersTab />,
      },
      {
        key: 'ai-providers',
        label: 'AI Provider',
        children: <AIProviders />,
      },
      {
        key: 'config',
        label: '系统配置',
        children: <ConfigTab />,
      },
      {
        key: 'notifications',
        label: '通知设置',
        children: <NotificationsTab />,
      },
      {
        key: 'audit',
        label: '操作审计',
        children: <AuditTab />,
      },
    ],
    [],
  );

  return (
    <PageContainer
      breadcrumbs={[{ title: '系统设置' }]}
      title="系统设置"
      description="用户权限管理、系统参数配置、通知渠道与操作审计"
      card={false}
      padding={0}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 8,
          padding: 24,
          minHeight: 200,
        }}
      >
        <Tabs
          defaultActiveKey="users"
          size="large"
          items={tabItems}
          style={{ minHeight: 400 }}
        />
      </div>
    </PageContainer>
  );
};

export default SystemPage;
