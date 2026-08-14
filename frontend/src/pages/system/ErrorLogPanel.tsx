import React, { useState } from 'react';
import {
  Table, Tag, Button, Space, Card, Row, Col, Statistic,
  Input, Select, DatePicker, Modal, Descriptions,
  Typography, Tooltip, Popconfirm, message, Divider,
} from 'antd';
import {
  SearchOutlined, ReloadOutlined, DeleteOutlined,
  EyeOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { systemApi } from '@/api/system';
import type { ErrorLogItem, ErrorLogStats } from '@/types/system';

const { Text, Title, Paragraph } = Typography;
const { RangePicker } = DatePicker;

const LEVEL_COLORS: Record<string, string> = {
  ERROR: 'red',
  WARNING: 'orange',
  INFO: 'blue',
};

const LEVEL_OPTIONS = [
  { label: '全部', value: '' },
  { label: 'ERROR', value: 'ERROR' },
  { label: 'WARNING', value: 'WARNING' },
  { label: 'INFO', value: 'INFO' },
];

const MODULE_OPTIONS = [
  { label: '全部', value: '' },
  { label: 'api', value: 'api' },
  { label: 'exchange', value: 'exchange' },
  { label: 'ai', value: 'ai' },
  { label: 'db', value: 'db' },
  { label: 'celery', value: 'celery' },
  { label: 'system', value: 'system' },
  { label: 'auth', value: 'auth' },
  { label: 'account', value: 'account' },
  { label: 'trade', value: 'trade' },
  { label: 'strategy', value: 'strategy' },
  { label: 'book', value: 'book' },
];

export const ErrorLogPanel: React.FC = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState({
    level: '',
    module: '',
    keyword: '',
    startTime: undefined as string | undefined,
    endTime: undefined as string | undefined,
  });
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [detailLog, setDetailLog] = useState<ErrorLogItem | null>(null);
  const [tracebackExpanded, setTracebackExpanded] = useState(false);

  // 查询错误日志列表
  const { data, isLoading, isRefetching } = useQuery({
    queryKey: ['error-logs', 'list', page, pageSize, filters],
    queryFn: () => systemApi.getErrorLogs({
      page,
      page_size: pageSize,
      ...filters,
    }),
  });

  // 查询统计
  const { data: stats } = useQuery({
    queryKey: ['error-logs', 'stats'],
    queryFn: () => systemApi.getErrorLogStats(),
    refetchInterval: 30000,
  });

  // 清理旧日志
  const cleanMutation = useMutation({
    mutationFn: (days: number) => systemApi.cleanErrorLogs({ before_days: days }),
    onSuccess: (res) => {
      message.success(`已清理 ${res?.deleted_count || 0} 条日志`);
      queryClient.invalidateQueries({ queryKey: ['error-logs'] });
    },
  });

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 160,
      render: (v: string) => dayjs(v).format('MM-DD HH:mm:ss'),
      sorter: true,
    },
    {
      title: '级别',
      dataIndex: 'level',
      width: 90,
      render: (v: string) => (
        <Tag color={LEVEL_COLORS[v] || 'default'}>{v}</Tag>
      ),
    },
    {
      title: '模块',
      dataIndex: 'module',
      width: 100,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '消息',
      dataIndex: 'message',
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <Text
            style={{
              maxWidth: 300,
              display: 'inline-block',
              fontFamily: 'monospace',
              fontSize: 12,
            }}
            ellipsis
          >
            {v}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '状态码',
      dataIndex: 'status_code',
      width: 80,
      render: (v: number) => {
        if (!v) return '-';
        const color = v >= 500 ? 'red' : v >= 400 ? 'orange' : 'green';
        return <Tag color={color}>{v}</Tag>;
      },
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      width: 80,
      render: (v: number) => {
        if (v == null) return '-';
        if (v > 1000) {
          return <Text type="danger">{(v / 1000).toFixed(1)}s</Text>;
        }
        return <Text type="secondary">{v.toFixed(0)}ms</Text>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: any, record: ErrorLogItem) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => {
            setDetailLog(record);
            setDetailModalOpen(true);
          }}
        />
      ),
    },
  ];

  return (
    <div>
      {/* 统计条 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="总错误数"
              value={stats?.total_errors || 0}
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="ERROR"
              value={stats?.error_count || 0}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="WARNING"
              value={stats?.warning_count || 0}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="模块分布"
              value={Object.keys(stats?.module_distribution || {}).length}
              suffix="个模块"
            />
          </Card>
        </Col>
      </Row>

      {/* 筛选栏 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder="日志级别"
            options={LEVEL_OPTIONS}
            value={filters.level}
            onChange={(v) => setFilters({ ...filters, level: v })}
            style={{ width: 120 }}
            allowClear
          />
          <Select
            placeholder="模块"
            options={MODULE_OPTIONS}
            value={filters.module}
            onChange={(v) => setFilters({ ...filters, module: v })}
            style={{ width: 120 }}
            allowClear
          />
          <Input
            placeholder="搜索关键词"
            prefix={<SearchOutlined />}
            value={filters.keyword}
            onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
            style={{ width: 200 }}
            allowClear
          />
          <RangePicker
            showTime
            onChange={(dates) => {
              setFilters({
                ...filters,
                startTime: dates?.[0]?.toISOString(),
                endTime: dates?.[1]?.toISOString(),
              });
            }}
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={() => { setPage(1); }}
          >
            搜索
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              setFilters({
                level: '', module: '',
                keyword: '', startTime: undefined, endTime: undefined,
              });
              setPage(1);
            }}
          >
            重置
          </Button>
          <Popconfirm
            title="确认清理 30 天前的错误日志？"
            onConfirm={() => cleanMutation.mutate(30)}
          >
            <Button
              icon={<DeleteOutlined />}
              danger
              loading={cleanMutation.isPending}
            >
              清理旧日志
            </Button>
          </Popconfirm>
        </Space>
      </Card>

      {/* 错误日志列表 */}
      <Table
        columns={columns}
        dataSource={data?.items || []}
        rowKey="id"
        loading={isLoading || isRefetching}
        pagination={{
          current: page,
          pageSize: pageSize,
          total: data?.total || 0,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          showSizeChanger: true,
          showQuickJumper: true,
          pageSizeOptions: ['10', '20', '50', '100'],
          showTotal: (total) => `共 ${total} 条`,
        }}
        scroll={{ x: 800 }}
        size="small"
      />

      {/* 详情弹窗 */}
      <Modal
        title="错误日志详情"
        open={detailModalOpen}
        onCancel={() => setDetailModalOpen(false)}
        width={800}
        footer={null}
      >
        {detailLog && (
          <>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="Request ID">
                <Text code style={{ fontSize: 12 }}>{detailLog.request_id || '-'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="级别">
                <Tag color={LEVEL_COLORS[detailLog.level]}>
                  {detailLog.level}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="模块">{detailLog.module}</Descriptions.Item>
              <Descriptions.Item label="状态码">
                <Tag color={detailLog.status_code >= 500 ? 'red' : 'orange'}>
                  {detailLog.status_code || '-'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="请求路径">
                <Text code>{detailLog.request_method} {detailLog.request_path}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="耗时">
                {detailLog.duration_ms != null
                  ? `${detailLog.duration_ms.toFixed(0)}ms`
                  : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="用户 IP">{detailLog.user_ip || '-'}</Descriptions.Item>
              <Descriptions.Item label="用户 ID">
                <Text code style={{ fontSize: 12 }}>{detailLog.user_id || '-'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="User-Agent" span={2}>
                <Text
                  style={{ fontSize: 12, wordBreak: 'break-all' }}
                  ellipsis={{ tooltip: detailLog.user_agent }}
                >
                  {detailLog.user_agent || '-'}
                </Text>
              </Descriptions.Item>
            </Descriptions>

            <Divider />

            <Title level={5}>错误消息</Title>
            <Paragraph
              style={{
                background: '#fff2f0',
                padding: 12,
                borderRadius: 6,
                fontFamily: 'monospace',
                fontSize: 13,
                whiteSpace: 'pre-wrap',
              }}
            >
              {detailLog.message}
            </Paragraph>

            {detailLog.exception_type && (
              <>
                <Title level={5}>异常类型</Title>
                <Tag color="red">{detailLog.exception_type}</Tag>
              </>
            )}

            {detailLog.traceback && (
              <>
                <Title level={5}>
                  <Space>
                    <span>异常栈</span>
                    <Button
                      size="small"
                      onClick={() => setTracebackExpanded(!tracebackExpanded)}
                    >
                      {tracebackExpanded ? '折叠' : '展开'}
                    </Button>
                    <Button
                      size="small"
                      onClick={() => {
                        navigator.clipboard.writeText(detailLog.traceback || '');
                        message.success('已复制到剪贴板');
                      }}
                    >
                      复制
                    </Button>
                  </Space>
                </Title>
                <Paragraph
                  style={{
                    background: '#f5f5f5',
                    padding: 12,
                    borderRadius: 6,
                    fontFamily: 'monospace',
                    fontSize: 11,
                    whiteSpace: 'pre-wrap',
                    maxHeight: tracebackExpanded ? 600 : 120,
                    overflow: 'auto',
                    lineHeight: 1.5,
                  }}
                >
                  {detailLog.traceback}
                </Paragraph>
              </>
            )}

            {detailLog.detail && (
              <>
                <Title level={5}>扩展信息</Title>
                <pre style={{
                  fontSize: 12, background: '#f5f5f5',
                  padding: 12, borderRadius: 6,
                  maxHeight: 200, overflow: 'auto',
                }}>
                  {JSON.stringify(detailLog.detail, null, 2)}
                </pre>
              </>
            )}
          </>
        )}
      </Modal>
    </div>
  );
};

export default ErrorLogPanel;