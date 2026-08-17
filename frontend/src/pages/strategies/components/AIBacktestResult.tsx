import React, { useState } from 'react';
import {
  Card, Row, Col, Statistic, Typography, Divider, Tag, Table, Space,
  Button, Empty, message, Timeline, Rate, Collapse, Segmented, Pagination,
} from 'antd';
import {
  ArrowUpOutlined, ArrowDownOutlined, DownloadOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type {
  AIBacktestDetail, AIBacktestTrade, AIAnalysisLogItem,
} from '@/types/ai-backtest';
import { TradeDetailModal } from './TradeDetailModal';

const { Title, Text, Paragraph } = Typography;

const DECISION_LABEL: Record<string, string> = {
  open_long: '开多', open_short: '开空', close_long: '平多', close_short: '平空', hold: '持有',
};
const DECISION_COLORS: Record<string, string> = {
  open_long: 'red', open_short: 'green', close_long: 'orange', close_short: 'orange', hold: 'default',
};
const TRIGGER_LABEL: Record<string, string> = {
  precheck_pass: '预筛通过', key_level_hit: '关键位触发', position_closed: '平仓触发', initial: '初始化', skipped: '跳过',
  trade_opened: '开单', trade_closed: '平仓',
};

interface Props {
  detail?: AIBacktestDetail;
  trades: AIBacktestTrade[];
  tradeTotal: number;
  onPageChange?: (page: number) => void;
  page?: number;
}

const PAGE_SIZE = 50;

const getTimelineColor = (log: AIAnalysisLogItem): string => {
  if (log.skipped) return 'gray';
  if (log.trade_info?.type === 'opened') return 'red';
  if (log.trade_info?.type === 'closed') return 'green';
  if (log.precheck) return 'cyan';
  if (log.trigger === 'key_level_hit') return 'magenta';
  if (log.trigger === 'position_closed') return 'orange';
  return 'blue';
};

export const AIBacktestResult: React.FC<Props> = ({
  detail, trades, tradeTotal, onPageChange, page = 1,
}) => {
  const [selectedTrade, setSelectedTrade] = useState<AIBacktestTrade | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [logFilter, setLogFilter] = useState<string>('analysis');
  const [logPage, setLogPage] = useState(1);

  if (!detail) {
    return <Empty description="暂无回测结果" />;
  }

  const summary = detail.result_summary;
  const isProfitable = (summary?.total_pnl || 0) >= 0;
  const aiAnalysisLogs = detail.ai_analysis_logs || [];
  const precheckTotal = detail.precheck_total ?? 0;
  const precheckTriggered = detail.precheck_triggered ?? 0;
  const savedCalls = Math.max(0, precheckTotal - precheckTriggered);

  // 过滤日志：仅分析 / 全部
  const analysisLogs = aiAnalysisLogs.filter((l) => !l.skipped);
  const filteredLogs = logFilter === 'analysis'
    ? analysisLogs
    : aiAnalysisLogs;
  const paginatedLogs = filteredLogs.slice(
    (logPage - 1) * PAGE_SIZE, logPage * PAGE_SIZE,
  );
  const totalLogPages = Math.ceil(filteredLogs.length / PAGE_SIZE);

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

      {/* AI 分析日志时间线（含跳过记录，支持过滤和分页） */}
      {aiAnalysisLogs.length > 0 && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            {/* 统计信息 + 过滤切换 */}
            <Space wrap>
              <Text strong>AI 分析日志</Text>
              <Tag color="blue">AI分析 {analysisLogs.length} 次</Tag>
              <Tag color="default">跳过 {aiAnalysisLogs.length - analysisLogs.length} 次</Tag>
              <Segmented
                size="small"
                value={logFilter}
                onChange={(val) => { setLogFilter(val as string); setLogPage(1); }}
                options={[
                  { label: `仅AI分析 (${analysisLogs.length})`, value: 'analysis' },
                  { label: `全部 (${aiAnalysisLogs.length})`, value: 'all' },
                ]}
              />
            </Space>

            {/* 时间线（分页显示） */}
            <Timeline
              items={paginatedLogs.map((log, logIdx) => {
                const a = log.analysis || {};
                const hasContent = a.summary || a.reasoning || a.stop_loss_method;
                const isSkipped = log.skipped;
                const ti = log.trade_info;
                const isLong = ti?.direction === 'long';
                return {
                  color: isSkipped ? 'gray' : getTimelineColor(log),
                  children: (
                    <div>
                      <Space wrap style={{ marginBottom: 4 }}>
                        <Tag>K线 #{log.kline_index}</Tag>
                        <Tag color={isSkipped ? 'default' : getTimelineColor(log)}>
                          {TRIGGER_LABEL[log.trigger] || log.trigger}
                        </Tag>
                        {log.trigger_reason && (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {log.trigger_reason}
                          </Text>
                        )}
                        {isSkipped && log.had_position && (
                          <Tag color="orange">持仓中</Tag>
                        )}
                        {!isSkipped && a.decision && (
                          <Tag color={DECISION_COLORS[a.decision] || 'default'}>
                            {DECISION_LABEL[a.decision] || a.decision}
                          </Tag>
                        )}
                        {!isSkipped && a.confidence != null && (
                          <Rate
                            disabled
                            allowHalf
                            value={a.confidence / 20}
                            style={{ fontSize: 12 }}
                          />
                        )}
                      </Space>
                      {/* 非跳过：显示完整分析详情 */}
                      {!isSkipped && (
                        <>
                          {/* 开单/平仓详情 */}
                          {ti && ti.type === 'opened' && (
                            <Card size="small" style={{ marginBottom: 8, background: '#fff7f0', borderColor: '#ffd591' }}>
                              <Space direction="vertical" style={{ width: '100%' }} size={4}>
                                <Space wrap>
                                  <Tag color={isLong ? 'red' : 'green'}>
                                    {isLong ? '开多' : '开空'}
                                  </Tag>
                                  <Text strong>开仓价: {ti.entry_price?.toFixed(2)}</Text>
                                  <Text>数量: {ti.quantity?.toFixed(4)}</Text>
                                </Space>
                                <Space wrap>
                                  {ti.stop_loss != null && (
                                    <Text type="danger" style={{ fontSize: 12 }}>
                                      止损: {ti.stop_loss?.toFixed(2)}
                                    </Text>
                                  )}
                                  {ti.take_profit != null && (
                                    <Text type="success" style={{ fontSize: 12 }}>
                                      止盈: {ti.take_profit?.toFixed(2)}
                                    </Text>
                                  )}
                                  {ti.risk_reward_ratio != null && (
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                      盈亏比: {ti.risk_reward_ratio}
                                    </Text>
                                  )}
                                  {ti.open_confidence != null && (
                                    <Rate
                                      disabled
                                      allowHalf
                                      value={ti.open_confidence / 20}
                                      style={{ fontSize: 12 }}
                                    />
                                  )}
                                  {ti.source_strategy && (
                                    <Tag color="blue" style={{ fontSize: 11 }}>
                                      策略: {ti.source_strategy}
                                    </Tag>
                                  )}
                                </Space>
                              </Space>
                            </Card>
                          )}
                          {ti && ti.type === 'closed' && (
                            <Card size="small" style={{ marginBottom: 8, background: '#f6ffed', borderColor: '#b7eb8f' }}>
                              <Space direction="vertical" style={{ width: '100%' }} size={4}>
                                <Space wrap>
                                  <Tag color={isLong ? 'red' : 'green'}>
                                    {isLong ? '平多' : '平空'}
                                  </Tag>
                                  <Text>开仓价: {ti.entry_price?.toFixed(2)}</Text>
                                  <Text>平仓价: {ti.exit_price?.toFixed(2)}</Text>
                                  <Text>数量: {ti.quantity?.toFixed(4)}</Text>
                                </Space>
                                <Space wrap>
                                  <Text
                                    strong
                                    style={{
                                      color: (ti.pnl || 0) >= 0 ? '#52c41a' : '#ff4d4f',
                                      fontSize: 14,
                                    }}
                                  >
                                    盈亏: {(ti.pnl || 0) >= 0 ? '+' : ''}{ti.pnl?.toFixed(2)} USDT
                                    {ti.pnl_pct != null && ` (${ti.pnl_pct?.toFixed(2)}%)`}
                                  </Text>
                                  {ti.holding_bars != null && (
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                      持仓: {ti.holding_bars} 根K线
                                    </Text>
                                  )}
                                </Space>
                                {ti.exit_reason && (
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    平仓原因: {ti.exit_reason}
                                  </Text>
                                )}
                              </Space>
                            </Card>
                          )}
                          {a.key_levels && a.key_levels.length > 0 && (
                            <Space wrap style={{ marginBottom: 4 }}>
                              {a.key_levels.map((lvl: any, idx: number) => (
                                <Tag key={idx} color={lvl.type === 'support' ? 'green' : 'red'}>
                                  {lvl.type === 'support' ? '支撑' : '阻力'}: {lvl.price}
                                </Tag>
                              ))}
                            </Space>
                          )}
                          {(a.stop_loss || a.take_profit) && (
                            <Space wrap style={{ marginBottom: 4 }}>
                              {a.stop_loss && <Text type="danger" style={{ fontSize: 12 }}>止损: {a.stop_loss}</Text>}
                              {a.take_profit && <Text type="success" style={{ fontSize: 12 }}>止盈: {a.take_profit}</Text>}
                              {a.stop_loss_method && <Text type="secondary" style={{ fontSize: 12 }}>方式: {a.stop_loss_method}</Text>}
                              {a.risk_reward_ratio && <Text type="secondary" style={{ fontSize: 12 }}>盈亏比: {a.risk_reward_ratio}</Text>}
                            </Space>
                          )}
                          {hasContent && (
                            <Collapse
                              ghost
                              size="small"
                              items={[{
                                key: logIdx,
                                label: <Text type="secondary" style={{ fontSize: 12 }}>查看完整分析</Text>,
                                children: (
                                  <div style={{ fontSize: 12 }}>
                                    {a.summary && (
                                      <div style={{ marginBottom: 8 }}>
                                        <Text strong>分析摘要: </Text>
                                        <Paragraph type="secondary" style={{ margin: '4px 0', whiteSpace: 'pre-wrap' }}>
                                          {a.summary}
                                        </Paragraph>
                                      </div>
                                    )}
                                    {a.reasoning && (
                                      <div style={{ marginBottom: 8 }}>
                                        <Text strong>决策理由: </Text>
                                        <Paragraph type="secondary" style={{ margin: '4px 0', whiteSpace: 'pre-wrap' }}>
                                          {a.reasoning}
                                        </Paragraph>
                                      </div>
                                    )}
                                    {a.trend && (
                                      <Text type="secondary">
                                        趋势: {a.trend === 'bullish' ? '看涨' : a.trend === 'bearish' ? '看跌' : '中性'}
                                      </Text>
                                    )}
                                  </div>
                                ),
                              }]} />
                          )}
                        </>
                      )}
                    </div>
                  ),
                };
              })}
            />

            {/* 分页控制 */}
            {totalLogPages > 1 && (
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <Pagination
                  size="small"
                  current={logPage}
                  total={filteredLogs.length}
                  pageSize={PAGE_SIZE}
                  showSizeChanger={false}
                  showTotal={(t) => `共 ${t} 条`}
                  onChange={(p) => setLogPage(p)}
                />
              </div>
            )}
          </Space>
        </Card>
      )}

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
