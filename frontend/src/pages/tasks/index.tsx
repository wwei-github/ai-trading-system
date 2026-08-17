import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Col,
  Row,
  Table,
  Tag,
  Typography,
  Space,
  Button,
  Popconfirm,
  Statistic,
  message,
  Empty,
  Tooltip,
  Modal,
} from 'antd';
import {
  DeleteOutlined,
  StopOutlined,
  ReloadOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import { PageContainer } from '@/components/Common';
import { taskApi, type QueuedTaskInfo } from '@/api/tasks';

const { Text, Title } = Typography;

const QUEUE_LABEL: Record<string, string> = {
  default: '默认队列',
  celery: 'Celery 队列',
};

const QUEUE_COLOR: Record<string, string> = {
  default: 'blue',
  celery: 'purple',
};

const TASK_NAME_LABEL: Record<string, string> = {
  'app.tasks.ai_backtest_tasks.run_ai_backtest': 'AI 回测',
  'app.tasks.book_tasks.parse_book': '书籍解析',
  'app.tasks.sync_tasks.sync_all_accounts': '同步账号',
  'app.tasks.sync_tasks.sync_trades': '同步交易',
  'app.tasks.sync_tasks.sync_asset_snapshot': '同步资产快照',
  'app.tasks.paper_trading_tasks.paper_trading_tick': '模拟交易',
  'app.tasks.paper_trading_tasks.live_signal_tick': '实盘信号',
  'app.tasks.report_tasks.generate_report': '生成报表',
  'app.tasks.ai_backtest_tasks.cleanup_stale_pending_backtests': '清理过期回测',
};

const getTaskLabel = (taskName: string): string => {
  return TASK_NAME_LABEL[taskName] || taskName.split('.').pop() || taskName;
};

const TasksPage = () => {
  const queryClient = useQueryClient();
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancelTarget, setCancelTarget] = useState<QueuedTaskInfo | null>(null);

  // 队列统计（自动刷新）
  const { data: stats } = useQuery({
    queryKey: ['task-queue-stats'],
    queryFn: () => taskApi.getQueueStats(),
    refetchInterval: 5000,
  });

  // 排队任务列表（自动刷新）
  const { data: queueData, isLoading } = useQuery({
    queryKey: ['task-queued'],
    queryFn: () => taskApi.getQueuedTasks(),
    refetchInterval: 5000,
  });

  const tasks = queueData?.tasks || [];

  // 删除排队任务
  const deleteMutation = useMutation({
    mutationFn: (taskId: string) => taskApi.deleteQueuedTask(taskId),
    onMutate: (taskId) => {
      setDeletingIds((prev) => new Set(prev).add(taskId));
    },
    onSuccess: () => {
      message.success('已从队列中删除任务');
      queryClient.invalidateQueries({ queryKey: ['task-queued'] });
      queryClient.invalidateQueries({ queryKey: ['task-queue-stats'] });
    },
    onError: () => {
      message.error('删除任务失败');
    },
    onSettled: (_, __, taskId) => {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(taskId);
        return next;
      });
    },
  });

  // 提取回测 ID（从任务名称和参数中）
  const extractBacktestId = (task: QueuedTaskInfo): string | null => {
    if (task.task_name === 'app.tasks.ai_backtest_tasks.run_ai_backtest') {
      // 回测 ID 通常在任务 ID 前缀或参数中，但这里我们直接使用任务名判断
      // 实际上回测 ID 是作为 task kwargs 传递的，在队列中不易提取
      return null;
    }
    return null;
  };

  // 判断是否为 AI 回测任务
  const isAiBacktest = (task: QueuedTaskInfo): boolean => {
    return task.task_name === 'app.tasks.ai_backtest_tasks.run_ai_backtest';
  };

  // 终止 AI 回测
  const cancelAiBacktestMutation = useMutation({
    mutationFn: (taskId: string) => {
      // 对于排队中的任务，直接从队列删除
      return deleteMutation.mutateAsync(taskId);
    },
    onSuccess: () => {
      message.success('已取消 AI 回测');
      queryClient.invalidateQueries({ queryKey: ['task-queued'] });
      queryClient.invalidateQueries({ queryKey: ['task-queue-stats'] });
    },
    onError: () => {
      message.error('取消 AI 回测失败');
    },
  });

  // 支持通过任务 ID 提取回测 ID（回测 ID 就是任务 ID 本身）
  const getBacktestId = (taskId: string): string => {
    return taskId;
  };

  const totalQueued = useMemo(() => {
    if (!stats?.queues) return 0;
    return Object.values(stats.queues).reduce((a: number, b: number) => a + b, 0);
  }, [stats]);

  const columns = [
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      width: 280,
      render: (name: string) => (
        <Space>
          <Tag color="blue">{getTaskLabel(name)}</Tag>
          <Tooltip title={name}>
            <Text type="secondary" style={{ fontSize: 12, maxWidth: 160 }} ellipsis>
              {name}
            </Text>
          </Tooltip>
        </Space>
      ),
    },
    {
      title: '任务 ID',
      dataIndex: 'task_id',
      key: 'task_id',
      width: 200,
      render: (id: string) => (
        <Text code style={{ fontSize: 11 }}>
          {id.substring(0, 24)}...
        </Text>
      ),
    },
    {
      title: '队列',
      dataIndex: 'queue_name',
      key: 'queue_name',
      width: 120,
      render: (q: string) => (
        <Tag color={QUEUE_COLOR[q] || 'default'}>
          {QUEUE_LABEL[q] || q}
        </Tag>
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_: any, r: QueuedTaskInfo) => {
        if (r.eta) {
          return (
            <Tag icon={<ClockCircleOutlined />} color="orange">
              定时执行
            </Tag>
          );
        }
        return (
          <Tag icon={<LoadingOutlined />} color="processing">
            排队中
          </Tag>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, r: QueuedTaskInfo) => {
        const isDeleting = deletingIds.has(r.task_id);
        const isAiBt = isAiBacktest(r);

        return (
          <Space>
            {isAiBt ? (
              <Popconfirm
                title="确认取消"
                description="将停止该 AI 回测任务"
                onConfirm={() => cancelAiBacktestMutation.mutate(r.task_id)}
                okText="确认"
                cancelText="取消"
              >
                <Button
                  size="small"
                  danger
                  icon={<StopOutlined />}
                  loading={isDeleting}
                >
                  取消
                </Button>
              </Popconfirm>
            ) : (
              <Popconfirm
                title="确认删除"
                description="将任务从队列中移除"
                onConfirm={() => deleteMutation.mutate(r.task_id)}
                okText="确认"
                cancelText="取消"
              >
                <Button
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  loading={isDeleting}
                >
                  删除
                </Button>
              </Popconfirm>
            )}
          </Space>
        );
      },
    },
  ];

  return (
    <PageContainer
      breadcrumbs={[{ title: '后台任务管理' }]}
      title="后台任务管理"
      description="查看和管理排队中的 Celery 后台任务"
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
        {/* 统计卡片 */}
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="队列总数"
                value={totalQueued}
                prefix={<ClockCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="default 队列"
                value={stats?.queues?.default ?? '-'}
                valueStyle={{ color: stats?.queues?.default ? '#1677ff' : undefined }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="celery 队列"
                value={stats?.queues?.celery ?? '-'}
                valueStyle={{ color: stats?.queues?.celery ? '#722ed1' : undefined }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Redis 连接"
                value={stats?.redis_connected ? '正常' : '断开'}
                valueStyle={{ color: stats?.redis_connected ? '#52c41a' : '#ff4d4f' }}
                prefix={stats?.redis_connected ? <CheckCircleOutlined /> : <MinusCircleOutlined />}
              />
            </Card>
          </Col>
        </Row>

        {/* 任务列表 */}
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Title level={5} style={{ margin: 0 }}>
              排队任务列表
            </Title>
            {tasks.length > 0 && (
              <Tag color="blue">{tasks.length} 个任务</Tag>
            )}
          </Space>
        </div>

        <Table
          dataSource={tasks}
          columns={columns}
          rowKey="task_id"
          loading={isLoading}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <Space direction="vertical" size={4}>
                    <Text type="secondary">没有排队中的任务</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      所有后台任务已处理完毕
                    </Text>
                  </Space>
                }
              />
            ),
          }}
          size="middle"
        />
      </div>
    </PageContainer>
  );
};

export default TasksPage;