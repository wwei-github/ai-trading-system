import React, { useState } from 'react';
import {
  Card, Row, Col, Statistic, Typography, Divider, Tag, Table, Space,
  Button, Empty, message,
} from 'antd';
import {
  ArrowUpOutlined, ArrowDownOutlined, DownloadOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type { AIBacktestDetail, AIBacktestTrade } from '@/types/ai-backtest';
import { TradeDetailModal } from './TradeDetailModal';

const { Title, Text } = Typography;

interface Props {
  detail?: AIBacktestDetail;
  trades: AIBacktestTrade[];
  tradeTotal: number;
  onPageChange?: (page: number) => void;
  page?: number;
}

export const AIBacktestResult: React.FC<Props> = ({ detail, trades, tradeTotal, onPageChange, page = 1 }) => {
  const [selectedTrade, setSelectedTrade] = useState<AIBacktestTrade | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  if (!detail) {
    return <Empty description="暂无回测结果" />;
  }

  const summary = detail.result_summary;
  const isProfitable = (summary?.total_pnl || 0) >= 0;

  return (
    <div>
      {/* 基本信息 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Text strong>{detail.strategy_name}</Text>
          <Tag>{detail.symbol}</Tag>
          <Tag>{detail.timeframe}</Tag>
          <Tag color={detail.status === 'completed' ? 'green' : 'red'}>
            {detail.status === 'completed' ? '已完成' : detail.status}
          </Tag>
          <Text type="secondary">
            开始: {dayjs(detail.start_time).format('YYYY-MM-DD HH:mm')}
          </Text>
          <Text type="secondary">
            K 线: {detail.completed_klines}/{detail.total_klines}
          </Text>
          {summary && (
            <Text type="secondary">
              AI 调用: {summary.ai_calls} 次
            </Text>
          )}
        </Space>
      </Card>

      {/* 指标卡片 */}
      {summary && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="总盈亏"
                value={summary.total_pnl}
                precision={2}
                suffix="USDT"
                valueStyle={{ color: isProfitable ? '#52c41a' : '#ff4d4f' }}
                prefix={isProfitable ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                收益率: {summary.total_return_pct}%
              </Text>
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="交易笔数" value={summary.total_trades} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                胜率: {summary.win_rate}%
              </Text>
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="最大回撤"
                value={summary.max_drawdown_pct}
                precision={2}
                suffix="%"
                valueStyle={{ color: '#faad14' }}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                最终权益: {summary.final_equity} USDT
              </Text>
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="平均盈亏"
                value={summary.avg_pnl}
                precision={2}
                suffix="USDT"
                valueStyle={{ color: summary.avg_pnl >= 0 ? '#52c41a' : '#ff4d4f' }}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                总手续费: {summary.total_fee} USDT
              </Text>
            </Card>
          </Col>
        </Row>
      )}

      {/* 平仓原因分布 */}
      {summary?.close_reasons && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space wrap>
            <Text strong>平仓原因分布: </Text>
            {Object.entries(summary.close_reasons).map(([reason, count]) => (
              <Tag key={reason}>
                {reason}: {count} 次
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      <Divider />

      {/* 交易明细 */}
      <Title level={5}>交易明细</Title>
      <Table
        dataSource={trades}
        rowKey="id"
        pagination={{
          current: page,
          total: tradeTotal,
          pageSize: 20,
          showSizeChanger: false,
          onChange: (p) => onPageChange?.(p),
        }}
        columns={[
          { title: '#', dataIndex: 'index', width: 60 },
          {
            title: '方向',
            dataIndex: 'direction',
            width: 80,
            render: (d) => (
              <Tag color={d === 'long' ? 'red' : 'green'}>
                {d === 'long' ? '做多' : '做空'}
              </Tag>
            ),
          },
          {
            title: '开仓时间',
            dataIndex: 'entry_time',
            render: (v) => dayjs(v).format('MM-DD HH:mm'),
          },
          {
            title: '开仓价',
            dataIndex: 'entry_price',
            render: (v) => v?.toFixed(2),
          },
          {
            title: '平仓价',
            dataIndex: 'exit_price',
            render: (v) => v?.toFixed(2) || '-',
          },
          {
            title: '盈亏',
            dataIndex: 'pnl',
            render: (v) => {
              if (v == null) return '-';
              return (
                <Text style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f' }}>
                  {v >= 0 ? '+' : ''}{v.toFixed(2)}
                </Text>
              );
            },
          },
          {
            title: '持仓',
            dataIndex: 'holding_bars',
            render: (v) => v ? `${v} 根` : '-',
          },
          {
            title: '操作',
            key: 'actions',
            width: 80,
            render: (_, record) => (
              <Button
                type="link"
                size="small"
                onClick={() => {
                  setSelectedTrade(record);
                  setModalOpen(true);
                }}
              >
                详情
              </Button>
            ),
          },
        ]}
      />

      {/* 导出按钮 */}
      <div style={{ marginTop: 16, textAlign: 'right' }}>
        <Button icon={<DownloadOutlined />} onClick={() => message.info('导出功能待实现')}>
          导出回测报告
        </Button>
      </div>

      {/* 交易详情弹窗 */}
      <TradeDetailModal
        open={modalOpen}
        trade={selectedTrade}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
};