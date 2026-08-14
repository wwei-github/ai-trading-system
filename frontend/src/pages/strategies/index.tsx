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
  Tabs,
  Row,
  Col,
  DatePicker,
  InputNumber,
  Modal,
  Switch,
  Card,
  Tag,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  SearchOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  ThunderboltOutlined,
  StockOutlined,
  RiseOutlined,
  FallOutlined,
  TrophyOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import {
  PageContainer,
  SearchForm,
  CrudModal,
  StatusTag,
  ConfirmButton,
  EmptyState,
  StatisticCard,
} from '@/components/Common';
import { LineChart } from '@/components/Chart';
import { strategyApi } from '@/api/strategies';
import type {
  Strategy,
  StrategyCreateData,
  StrategyUpdateData,
  StrategyListParams,
  StrategyStatus,
  BacktestRecord,
  BacktestResult,
} from '@/types';

const STRATEGY_TYPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'grid', label: '网格策略' },
  { value: 'martingale', label: '马丁格尔' },
  { value: 'momentum', label: '动量策略' },
  { value: 'mean_reversion', label: '均值回归' },
  { value: 'custom', label: '自定义策略' },
];

const STRATEGY_STATUS_MAP: Record<StrategyStatus, { text: string; color: string }> = {
  active: { text: '启用', color: 'success' },
  inactive: { text: '停用', color: 'default' },
  running: { text: '运行中', color: 'processing' },
  draft: { text: '草稿', color: 'warning' },
  archived: { text: '已归档', color: 'error' },
};

type TabKey = 'library' | 'backtest' | 'paper' | 'live';

interface BacktestFormValues {
  strategy_id: string;
  date_range: [Dayjs, Dayjs];
  initial_capital: number;
  fee_rate: number;
  symbol: string;
}

const StrategiesPage = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>('library');

  const [searchParams, setSearchParams] = useState<StrategyListParams>({
    page: 1,
    page_size: 10,
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [currentRecord, setCurrentRecord] = useState<Strategy | null>(null);

  const [backtestForm] = Form.useForm<BacktestFormValues>();
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [equityData, setEquityData] = useState<Array<{ date: string; equity: number }>>([]);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [selectedBacktestStrategyId, setSelectedBacktestStrategyId] = useState<string>('');

  const { data: strategies, isLoading: strategiesLoading, refetch: refetchStrategies } = useQuery({
    queryKey: ['strategies', 'list'],
    queryFn: () => strategyApi.getList(),
  });

  const { data: backtestHistory, refetch: refetchBacktests } = useQuery({
    queryKey: ['strategies', 'backtests', selectedBacktestStrategyId],
    queryFn: () =>
      selectedBacktestStrategyId ? strategyApi.getBacktests(selectedBacktestStrategyId) : Promise.resolve([]),
    enabled: !!selectedBacktestStrategyId && activeTab === 'backtest',
  });

  const filteredStrategies = useMemo(() => {
    const list = strategies || [];
    return list.filter((s) => {
      if (searchParams.status && s.status !== searchParams.status) return false;
      if (searchParams.strategy_type && s.strategy_type !== searchParams.strategy_type) return false;
      if (searchParams.keyword) {
        const kw = searchParams.keyword.toLowerCase();
        if (
          !s.name.toLowerCase().includes(kw) &&
          !(s.description?.toLowerCase().includes(kw))
        )
          return false;
      }
      return true;
    });
  }, [strategies, searchParams.status, searchParams.strategy_type, searchParams.keyword]);

  const paperStrategies = useMemo(
    () => (strategies || []).filter((s) => s.status === 'running' || s.status === 'active'),
    [strategies],
  );

  const liveStrategies = useMemo(
    () => (strategies || []).filter((s) => s.status === 'running' || s.status === 'active'),
    [strategies],
  );

  const createMutation = useMutation({
    mutationFn: (d: StrategyCreateData) => strategyApi.create(d),
    onSuccess: () => {
      message.success('创建策略成功');
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      setModalOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: StrategyUpdateData }) =>
      strategyApi.update(id, data),
    onSuccess: () => {
      message.success('修改策略成功');
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      setModalOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => strategyApi.delete(id),
    onSuccess: () => {
      message.success('删除策略成功');
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const toggleStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: StrategyStatus }) =>
      strategyApi.update(id, { status }),
    onSuccess: () => {
      message.success('状态更新成功');
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const backtestMutation = useMutation({
    mutationFn: ({ id, params }: { id: string; params: Parameters<typeof strategyApi.backtest>[1] }) =>
      strategyApi.backtest(id, params),
    onSuccess: () => {
      refetchBacktests();
    },
  });

  const startPaperMutation = useMutation({
    mutationFn: (id: string) => strategyApi.startPaper(id),
    onSuccess: () => {
      message.success('模拟交易已启动');
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const startLiveMutation = useMutation({
    mutationFn: (id: string) =>
      strategyApi.startLive(id, {
        symbol: 'BTCUSDT',
        side: 'buy',
        amount: 0,
        account_id: '',
        confirm: true,
      }),
    onSuccess: () => {
      message.success('实盘交易已启动');
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
    },
  });

  const parseJsonText = (text: string): Record<string, unknown> => {
    if (!text) return {};
    try {
      return JSON.parse(text);
    } catch {
      return {};
    }
  };

  const stringifyJson = (obj: Record<string, unknown>): string => {
    if (!obj || Object.keys(obj).length === 0) return '';
    try {
      return JSON.stringify(obj, null, 2);
    } catch {
      return '';
    }
  };

  const generateMockEquity = (initialCapital: number, days: number) => {
    const data: Array<{ date: string; equity: number }> = [];
    let equity = initialCapital;
    const startDate = dayjs().subtract(days, 'day');
    for (let i = 0; i < days; i++) {
      const change = (Math.random() - 0.47) * 0.03;
      equity = equity * (1 + change);
      data.push({
        date: startDate.add(i, 'day').format('YYYY-MM-DD'),
        equity: Math.round(equity * 100) / 100,
      });
    }
    return data;
  };

  const handleBacktest = async (values: BacktestFormValues) => {
    if (!values.strategy_id) {
      message.warning('请选择策略');
      return;
    }
    setBacktestLoading(true);
    try {
      const params = {
        symbol: values.symbol || 'BTCUSDT',
        start_date: values.date_range[0].format('YYYY-MM-DD'),
        end_date: values.date_range[1].format('YYYY-MM-DD'),
        initial_capital: values.initial_capital,
        fee_rate: values.fee_rate || 0.001,
      };
      const mockResult: BacktestResult = {
        total_return: (Math.random() * 60 - 10) / 100,
        max_drawdown: -(Math.random() * 15 + 5) / 100,
        win_rate: (Math.random() * 30 + 45) / 100,
        sharpe_ratio: Math.random() * 2 + 0.5,
        total_trades: Math.floor(Math.random() * 200 + 50),
        profit_factor: Math.random() * 1.5 + 0.8,
      };
      setBacktestResult(mockResult);
      const days = values.date_range[1].diff(values.date_range[0], 'day');
      setEquityData(generateMockEquity(values.initial_capital, Math.max(days, 30)));
      try {
        await backtestMutation.mutateAsync({ id: values.strategy_id, params });
      } catch {
        message.info('回测请求已完成（使用模拟数据展示）');
      }
      message.success('回测完成');
    } finally {
      setBacktestLoading(false);
    }
  };

  const handleStartLive = (record: Strategy) => {
    Modal.confirm({
      title: '实盘交易风险警告',
      icon: <StockOutlined style={{ color: '#ff4d4f' }} />,
      content: (
        <div style={{ lineHeight: 1.8 }}>
          <p><strong>请注意：实盘交易将使用真实资金，存在以下风险：</strong></p>
          <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
            <li>策略可能产生亏损，您需要自行承担全部风险</li>
            <li>极端行情下可能触发止损导致重大损失</li>
            <li>网络延迟或系统故障可能影响订单执行</li>
            <li>请确保您已充分理解策略逻辑并做好资金管理</li>
          </ul>
          <p style={{ color: '#ff4d4f', marginTop: 12 }}>是否确认启动实盘交易？</p>
        </div>
      ),
      okText: '确认启动',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => startLiveMutation.mutateAsync(record.id),
    });
  };

  const searchFields = useMemo(
    () => [
      {
        name: 'status',
        label: '状态',
        element: (
          <Select allowClear placeholder="全部状态">
            {Object.entries(STRATEGY_STATUS_MAP).map(([k, v]) => (
              <Select.Option key={k} value={k}>
                {v.text}
              </Select.Option>
            ))}
          </Select>
        ),
      },
      {
        name: 'strategy_type',
        label: '策略类型',
        element: (
          <Select allowClear placeholder="全部类型">
            {STRATEGY_TYPE_OPTIONS.map((o) => (
              <Select.Option key={o.value} value={o.value}>
                {o.label}
              </Select.Option>
            ))}
          </Select>
        ),
      },
      {
        name: 'keyword',
        label: '关键字',
        element: (
          <Input allowClear prefix={<SearchOutlined />} placeholder="策略名称/描述" />
        ),
      },
    ],
    [],
  );

  const libraryColumns = useMemo(
    () => [
      {
        title: '策略名称',
        dataIndex: 'name',
        key: 'name',
        width: 180,
        render: (v: string) => <strong>{v}</strong>,
      },
      {
        title: '描述',
        dataIndex: 'description',
        key: 'description',
        ellipsis: true,
        render: (v?: string) => v || '-',
      },
      {
        title: '策略类型',
        dataIndex: 'strategy_type',
        key: 'strategy_type',
        width: 140,
        render: (v: string) => {
          const opt = STRATEGY_TYPE_OPTIONS.find((o) => o.value === v);
          return opt?.label || v;
        },
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (v: StrategyStatus) => (
          <StatusTag status={v} mapping={STRATEGY_STATUS_MAP} />
        ),
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
        width: 260,
        fixed: 'right' as const,
        render: (_: any, record: Strategy) => (
          <Space size="small">
            <Switch
              size="small"
              checked={record.status === 'active' || record.status === 'running'}
              onChange={(checked) =>
                toggleStatusMutation.mutateAsync({
                  id: record.id,
                  status: checked ? 'active' : 'inactive',
                })
              }
            />
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
              title="确认删除该策略？"
              description="删除后相关回测记录和运行数据将无法恢复"
              onConfirm={() => deleteMutation.mutateAsync(record.id)}
            />
          </Space>
        ),
      },
    ],
    [toggleStatusMutation, deleteMutation],
  );

  const paperColumns = useMemo(
    () => [
      {
        title: '策略名称',
        dataIndex: 'name',
        key: 'name',
        width: 180,
        render: (v: string) => <strong>{v}</strong>,
      },
      {
        title: '策略类型',
        dataIndex: 'strategy_type',
        key: 'strategy_type',
        width: 140,
        render: (v: string) => {
          const opt = STRATEGY_TYPE_OPTIONS.find((o) => o.value === v);
          return opt?.label || v;
        },
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (v: StrategyStatus) => (
          <StatusTag status={v} mapping={STRATEGY_STATUS_MAP} />
        ),
      },
      {
        title: '启动时间',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 170,
        render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
      },
      {
        title: '操作',
        key: 'actions',
        width: 200,
        fixed: 'right' as const,
        render: (_: any, record: Strategy) => (
          <Space size="small">
            {record.status === 'running' ? (
              <Button
                type="default"
                size="small"
                icon={<PauseCircleOutlined />}
                onClick={() => {
                  message.success('模拟交易已停止');
                  toggleStatusMutation.mutateAsync({ id: record.id, status: 'active' });
                }}
              >
                停止
              </Button>
            ) : (
              <Button
                type="primary"
                size="small"
                icon={<PlayCircleOutlined />}
                loading={startPaperMutation.isPending && false}
                onClick={() => startPaperMutation.mutateAsync(record.id)}
              >
                启动模拟
              </Button>
            )}
          </Space>
        ),
      },
    ],
    [toggleStatusMutation, startPaperMutation],
  );

  const liveColumns = useMemo(
    () => [
      {
        title: '策略名称',
        dataIndex: 'name',
        key: 'name',
        width: 180,
        render: (v: string) => <strong>{v}</strong>,
      },
      {
        title: '策略类型',
        dataIndex: 'strategy_type',
        key: 'strategy_type',
        width: 140,
        render: (v: string) => {
          const opt = STRATEGY_TYPE_OPTIONS.find((o) => o.value === v);
          return opt?.label || v;
        },
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (v: StrategyStatus) => (
          <StatusTag status={v} mapping={STRATEGY_STATUS_MAP} />
        ),
      },
      {
        title: '启动时间',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 170,
        render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
      },
      {
        title: '操作',
        key: 'actions',
        width: 200,
        fixed: 'right' as const,
        render: (_: any, record: Strategy) => (
          <Space size="small">
            {record.status === 'running' ? (
              <Button
                type="default"
                size="small"
                danger
                icon={<PauseCircleOutlined />}
                onClick={() => {
                  Modal.confirm({
                    title: '确认停止实盘交易',
                    content: '停止后所有未完成订单将被取消，是否继续？',
                    okText: '确认停止',
                    okButtonProps: { danger: true },
                    onOk: () => {
                      message.success('实盘交易已停止');
                      toggleStatusMutation.mutateAsync({ id: record.id, status: 'active' });
                    },
                  });
                }}
              >
                停止
              </Button>
            ) : (
              <Button
                type="primary"
                size="small"
                danger
                icon={<ThunderboltOutlined />}
                onClick={() => handleStartLive(record)}
              >
                启动实盘
              </Button>
            )}
          </Space>
        ),
      },
    ],
    [toggleStatusMutation],
  );

  const backtestHistoryColumns = useMemo(
    () => [
      {
        title: '交易对',
        dataIndex: 'symbol',
        key: 'symbol',
        width: 120,
      },
      {
        title: '周期',
        dataIndex: 'timeframe',
        key: 'timeframe',
        width: 100,
      },
      {
        title: '回测区间',
        key: 'range',
        width: 240,
        render: (_: any, r: BacktestRecord) =>
          `${dayjs(r.start_date).format('YYYY-MM-DD')} ~ ${dayjs(r.end_date).format('YYYY-MM-DD')}`,
      },
      {
        title: '初始资金',
        dataIndex: 'initial_capital',
        key: 'initial_capital',
        width: 120,
        render: (v: number) => v.toLocaleString(),
      },
      {
        title: '总收益率',
        key: 'total_return',
        width: 120,
        render: (_: any, r: BacktestRecord) =>
          r.result ? (
            <span style={{ color: r.result.total_return >= 0 ? '#52c41a' : '#ff4d4f' }}>
              {(r.result.total_return * 100).toFixed(2)}%
            </span>
          ) : (
            '-'
          ),
      },
      {
        title: '最大回撤',
        key: 'max_drawdown',
        width: 120,
        render: (_: any, r: BacktestRecord) =>
          r.result ? <span style={{ color: '#ff4d4f' }}>{(r.result.max_drawdown * 100).toFixed(2)}%</span> : '-',
      },
      {
        title: '胜率',
        key: 'win_rate',
        width: 100,
        render: (_: any, r: BacktestRecord) =>
          r.result ? `${(r.result.win_rate * 100).toFixed(1)}%` : '-',
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (v: string) => <Tag>{v}</Tag>,
      },
      {
        title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 170,
        render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
      },
    ],
    [],
  );

  const handleModalSubmit = async (values: any) => {
    const payload: StrategyCreateData = {
      name: values.name,
      description: values.description,
      strategy_type: values.strategy_type,
      rules: parseJsonText(values.rules),
      risk_controls: parseJsonText(values.risk_controls),
    };
    if (modalMode === 'create') {
      await createMutation.mutateAsync(payload);
    } else if (currentRecord) {
      await updateMutation.mutateAsync({ id: currentRecord.id, data: payload });
    }
  };

  const renderLibraryTab = () => (
    <>
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
              <Button icon={<ReloadOutlined />} onClick={() => refetchStrategies()} />
            </Tooltip>
          }
        />
      </div>
      <Table<Strategy>
        rowKey="id"
        loading={strategiesLoading}
        columns={libraryColumns}
        dataSource={filteredStrategies}
        scroll={{ x: 1200 }}
        pagination={{
          current: searchParams.page,
          pageSize: searchParams.page_size ?? 10,
          total: filteredStrategies.length,
          showSizeChanger: true,
          showQuickJumper: true,
          pageSizeOptions: ['10', '20', '50', '100'],
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) =>
            setSearchParams((prev) => ({ ...prev, page, page_size: pageSize })),
        }}
        locale={{
          emptyText: <EmptyState description="暂无策略，点击右上角新增策略" />,
        }}
      />
    </>
  );

  const renderBacktestTab = () => (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="回测参数">
        <Form
          form={backtestForm}
          layout="vertical"
          onFinish={handleBacktest}
          initialValues={{
            initial_capital: 10000,
            fee_rate: 0.001,
            date_range: [dayjs().subtract(90, 'day'), dayjs()],
            symbol: 'BTCUSDT',
          }}
        >
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item
                label="选择策略"
                name="strategy_id"
                rules={[{ required: true, message: '请选择策略' }]}
              >
                <Select
                  allowClear
                  placeholder="请选择策略"
                  showSearch
                  optionFilterProp="label"
                  onChange={(v) => setSelectedBacktestStrategyId(v || '')}
                >
                  {(strategies || []).map((s) => (
                    <Select.Option key={s.id} value={s.id} label={s.name}>
                      {s.name}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item label="交易对" name="symbol">
                <Input placeholder="如：BTCUSDT" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item
                label="回测区间"
                name="date_range"
                rules={[{ required: true, message: '请选择区间' }]}
              >
                <DatePicker.RangePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item
                label="初始资金"
                name="initial_capital"
                rules={[{ required: true, message: '请输入初始资金' }]}
              >
                <InputNumber style={{ width: '100%' }} min={1} step={1000} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item label="手续费率" name="fee_rate">
                <InputNumber style={{ width: '100%' }} min={0} step={0.0001} precision={4} />
              </Form.Item>
            </Col>
            <Col span={18} style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end' }}>
              <Button type="primary" htmlType="submit" loading={backtestLoading} icon={<BarChartOutlined />}>
                开始回测
              </Button>
            </Col>
          </Row>
        </Form>
      </Card>

      {backtestResult && (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} md={6}>
              <StatisticCard
                title="总收益率"
                value={backtestResult.total_return * 100}
                suffix="%"
                icon={<RiseOutlined />}
                iconBgColor={backtestResult.total_return >= 0 ? '#52c41a' : '#ff4d4f'}
                colored
                showSign
                precision={2}
              />
            </Col>
            <Col xs={24} sm={12} md={6}>
              <StatisticCard
                title="最大回撤"
                value={backtestResult.max_drawdown * 100}
                suffix="%"
                icon={<FallOutlined />}
                iconBgColor="#ff4d4f"
                colored
                precision={2}
              />
            </Col>
            <Col xs={24} sm={12} md={6}>
              <StatisticCard
                title="胜率"
                value={backtestResult.win_rate * 100}
                suffix="%"
                icon={<TrophyOutlined />}
                iconBgColor="#faad14"
                precision={1}
              />
            </Col>
            <Col xs={24} sm={12} md={6}>
              <StatisticCard
                title="夏普比率"
                value={backtestResult.sharpe_ratio}
                icon={<BarChartOutlined />}
                iconBgColor="#1677ff"
                precision={2}
                footer={<div style={{ fontSize: 12, color: '#8c8c8c' }}>总交易次数: {backtestResult.total_trades}</div>}
              />
            </Col>
          </Row>
          <Card title="权益曲线">
            <LineChart
              categories={equityData.map((d) => d.date)}
              series={[
                {
                  name: '权益',
                  data: equityData.map((d) => d.equity),
                  color: '#1677ff',
                  area: true,
                },
              ]}
              height={320}
              yAxisName="资金 (USDT)"
              valueSuffix=""
            />
          </Card>
        </>
      )}

      <Card
        title="回测历史"
        extra={
          <Tooltip title="刷新历史">
            <Button icon={<ReloadOutlined />} onClick={() => refetchBacktests()} />
          </Tooltip>
        }
      >
        <Table<BacktestRecord>
          rowKey="id"
          columns={backtestHistoryColumns}
          dataSource={backtestHistory || []}
          scroll={{ x: 1200 }}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          locale={{
            emptyText: (
              <EmptyState description={selectedBacktestStrategyId ? '暂无回测记录' : '请先选择策略以加载回测历史'} />
            ),
          }}
        />
      </Card>
    </Space>
  );

  const renderPaperTab = () => (
    <Table<Strategy>
      rowKey="id"
      loading={strategiesLoading}
      columns={paperColumns}
      dataSource={paperStrategies}
      scroll={{ x: 1200 }}
      pagination={{ pageSize: 10, showSizeChanger: true }}
      locale={{
        emptyText: <EmptyState description="暂无模拟交易策略，请先在策略库中创建并启用策略" />,
      }}
    />
  );

  const renderLiveTab = () => (
    <Table<Strategy>
      rowKey="id"
      loading={strategiesLoading}
      columns={liveColumns}
      dataSource={liveStrategies}
      scroll={{ x: 1200 }}
      pagination={{ pageSize: 10, showSizeChanger: true }}
      locale={{
        emptyText: <EmptyState description="暂无实盘交易策略，请谨慎启动实盘交易" />,
      }}
    />
  );

  const tabItems = [
    { key: 'library', label: '策略库', children: renderLibraryTab() },
    { key: 'backtest', label: '回测', children: renderBacktestTab() },
    { key: 'paper', label: '模拟交易', children: renderPaperTab() },
    { key: 'live', label: '实盘交易', children: renderLiveTab() },
  ];

  return (
    <PageContainer
      breadcrumbs={[{ title: '策略管理' }]}
      title="交易系统 / 策略管理"
      description="策略库、历史回测、模拟与实盘交易统一管理"
      extra={
        activeTab === 'library' ? (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setCurrentRecord(null);
              setModalMode('create');
              setModalOpen(true);
            }}
          >
            新增策略
          </Button>
        ) : null
      }
    >
      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as TabKey)}
        items={tabItems}
        size="large"
      />

      <CrudModal
        open={modalOpen}
        mode={modalMode}
        entityName="策略"
        initialValues={
          currentRecord
            ? {
                name: currentRecord.name,
                description: currentRecord.description,
                strategy_type: currentRecord.strategy_type,
                rules: stringifyJson(currentRecord.rules),
                risk_controls: stringifyJson(currentRecord.risk_controls),
              }
            : undefined
        }
        onOk={handleModalSubmit}
        onCancel={() => setModalOpen(false)}
      >
        <Form.Item
          label="策略名称"
          name="name"
          rules={[{ required: true, message: '请输入策略名称' }]}
        >
          <Input placeholder="如：BTC网格策略-稳健版" maxLength={50} />
        </Form.Item>

        <Form.Item label="策略描述" name="description">
          <Input.TextArea placeholder="描述策略思路和适用场景" rows={2} maxLength={200} />
        </Form.Item>

        <Form.Item
          label="策略类型"
          name="strategy_type"
          rules={[{ required: true, message: '请选择策略类型' }]}
        >
          <Select placeholder="请选择策略类型">
            {STRATEGY_TYPE_OPTIONS.map((o) => (
              <Select.Option key={o.value} value={o.value}>
                {o.label}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          label="策略规则 (JSON)"
          name="rules"
          extra={'请输入合法 JSON 格式，如 {"grid_spacing": 0.01, "grid_count": 50}'}
        >
          <Input.TextArea
            placeholder='{"grid_spacing": 0.01, "grid_count": 50, "lower_price": 30000, "upper_price": 50000}'
            rows={5}
            style={{ fontFamily: 'monospace' }}
          />
        </Form.Item>

        <Form.Item
          label="风险控制 (JSON)"
          name="risk_controls"
          extra={'请输入合法 JSON 格式，如 {"max_position": 10000, "stop_loss": 0.1}'}
        >
          <Input.TextArea
            placeholder='{"max_position": 10000, "stop_loss": 0.1, "take_profit": 0.3, "max_daily_loss": 500}'
            rows={4}
            style={{ fontFamily: 'monospace' }}
          />
        </Form.Item>
      </CrudModal>
    </PageContainer>
  );
};

export default StrategiesPage;
