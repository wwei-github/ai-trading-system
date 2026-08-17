import React, { useCallback } from 'react';
import { Table, Tag, Button, Space, Typography, Popconfirm, message } from 'antd';
import { EyeOutlined, StopOutlined, MinusCircleOutlined } from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import { aiBacktestApi } from '@/api/ai-backtest';
import type { AIBacktestHistoryItem } from '@/types/ai-backtest';

const { Text } = Typography;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待开始', color: 'default' },
  running: { label: '运行中', color: 'processing' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
  cancelled: { label: '已取消', color: 'warning' },
  cancelling: { label: '终止中', color: 'warning' },
};

interface Props {
  onSelect: (id: string) => void;
}

export const AIBacktestHistory: React.FC<Props> = ({ onSelect }) => {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const [stoppingIds, setStoppingIds] = React.useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery({
    queryKey: ['ai-backtest', 'history', page],
    queryFn: () => aiBacktestApi.getHistory(page),
  });

  const handleStop = useCallback(async (record: AIBacktestHistoryItem) => {
    setStoppingIds(prev => new Set(prev).add(record.id));
    try {
      if (record.status === 'pending') {
        await aiBacktestApi.cancel(record.id);
        message.success('已取消回测');
      } else {
        await aiBacktestApi.stop(record.id);
        message.success('已发送终止指令');
      }
      // 刷新列表
      queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'history'] });
      queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'detail'] });
    } catch (err: any) {
      const msg = err?.response?.data?.message || err?.message || '操作失败';
      message.error(msg);
    } finally {
      setStoppingIds(prev => {
        const next = new Set(prev);
        next.delete(record.id);
        return next;
      });
    }
  }, [queryClient]);

  const columns = [
    {
      title: '策略',
      dataIndex: 'strategy_name',
      width: 150,
    },
    {
      title: '交易对/周期',
      key: 'symbol',
      width: 120,
      render: (_: any, r: AIBacktestHistoryItem) => (
        <Space size={4}>
          <Text>{r.symbol}</Text>
          <Text type="secondary">{r.timeframe}</Text>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: string) => {
        const m = STATUS_MAP[s] || { label: s, color: 'default' };
        return <Tag color={m.color}>{m.label}</Tag>;
      },
    },
    {
      title: '完成进度',
      key: 'progress',
      width: 120,
      render: (_: any, r: AIBacktestHistoryItem) =>
        `${r.completed_klines}/${r.total_klines}`,
    },
    {
      title: '总盈亏',
      dataIndex: 'total_pnl',
      width: 120,
      render: (v: number | null) => {
        if (v == null) return '-';
        return (
          <Text style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f' }}>
            {v >= 0 ? '+' : ''}{v.toFixed(2)}
          </Text>
        );
      },
    },
    {
      title: '胜率',
      dataIndex: 'win_rate',
      width: 80,
      render: (v: number | null) => v != null ? `${v}%` : '-',
    },
    {
      title: '交易数',
      dataIndex: 'trade_count',
      width: 80,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 160,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_: any, record: AIBacktestHistoryItem) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => onSelect(record.id)}
          >
            查看
          </Button>
          {(record.status === 'pending' || record.status === 'running') && (
            <Popconfirm
              title={
                record.status === 'pending'
                  ? '确定要取消此回测吗？'
                  : '确定要终止此回测吗？'
              }
              onConfirm={() => handleStop(record)}
              okText="确定"
              cancelText="取消"
            >
              <Button
                type="link"
                size="small"
                danger
                icon={record.status === 'pending' ? <MinusCircleOutlined /> : <StopOutlined />}
                loading={stoppingIds.has(record.id)}
              >
                {record.status === 'pending' ? '取消' : '终止'}
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={data?.data?.items || []}
      rowKey="id"
      loading={isLoading}
      pagination={{
        current: page,
        pageSize: 10,
        total: data?.data?.total || 0,
        onChange: setPage,
        showSizeChanger: false,
      }}
      scroll={{ x: 1100 }}
    />
  );
};