import React from 'react';
import {
  Card,
  Progress,
  Space,
  Typography,
  Spin,
  Tag,
  Statistic,
  Descriptions,
  Button,
  Alert,
  Row,
  Col,
  Rate,
} from 'antd';
import { StopOutlined } from '@ant-design/icons';
import type {
  AIBacktestProgress as AIBacktestProgressType,
  AIBacktestAIAnalysis,
  KeyLevel,
} from '@/types/ai-backtest';

const { Text, Title, Paragraph } = Typography;

const STAGE_LABEL: Record<string, string> = {
  pending: '排队等待',
  preheat: '预热数据获取',
  running: '逐根推进中',
  summary: '生成总结报告',
  done: '完成',
  error: '失败',
  cancelled: '已取消',
};

const TREND_MAP: Record<string, { label: string; color: string }> = {
  bullish: { label: '看涨', color: 'red' },
  bearish: { label: '看跌', color: 'green' },
  neutral: { label: '中性', color: 'default' },
};

const DECISION_MAP: Record<string, { label: string; color: string }> = {
  open_long: { label: '开多', color: 'red' },
  open_short: { label: '开空', color: 'green' },
  close_long: { label: '平多', color: 'orange' },
  close_short: { label: '平空', color: 'orange' },
  hold: { label: '持有', color: 'default' },
};

const TRIGGER_REASON_MAP: Record<string, { label: string; color: string }> = {
  precheck_pass: { label: '预筛通过', color: 'blue' },
  key_level_hit: { label: '关键位触发', color: 'magenta' },
  position_closed: { label: '持仓平仓', color: 'orange' },
  initial: { label: '初始分析', color: 'purple' },
};

interface Props {
  progress: AIBacktestProgressType | null;
  aiAnalysis?: AIBacktestAIAnalysis | null;
  isStopping?: boolean;
  onStop?: () => void;
}

export const AIBacktestProgress: React.FC<Props> = ({
  progress,
  aiAnalysis,
  isStopping,
  onStop,
}) => {
  if (!progress) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text>正在启动回测...</Text>
        </div>
      </div>
    );
  }

  const isError = progress.stage === 'error';
  const isDone = progress.stage === 'done';
  const isCancelled = progress.stage === 'cancelled';
  const isRunning =
    progress.stage === 'running' || progress.stage === 'preheat' || progress.stage === 'summary';
  const stageColor = isError ? 'red' : isDone ? 'green' : isCancelled ? 'orange' : 'blue';

  // 统计信息
  const aiCallCount = progress.ai_call_count ?? 0;
  // 当前权益
  const currentEquity = progress.current_equity ?? 0;
  const initialCapital = progress.initial_capital ?? 10000;
  const equityChange = currentEquity - initialCapital;
  const equityChangePct = initialCapital > 0 ? ((equityChange / initialCapital) * 100).toFixed(2) : '0.00';

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 24 }}>
      <Title level={4} style={{ textAlign: 'center' }}>
        AI 回测进度
      </Title>

      {/* 进度条 */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Tag color={stageColor}>{STAGE_LABEL[progress.stage] || progress.stage}</Tag>
        </div>

        <Progress
          percent={Math.round(progress.progress)}
          status={isError ? 'exception' : isDone ? 'success' : 'active'}
          strokeColor={{
            '0%': '#1677ff',
            '100%': isDone ? '#52c41a' : '#1677ff',
          }}
        />

        <div style={{ marginTop: 16 }}>
          <Space size="large" style={{ justifyContent: 'center', width: '100%' }}>
            <Statistic
              title="推进进度"
              value={progress.current_kline}
              suffix={`/ ${progress.total_klines}`}
            />
            <Statistic title="已产生交易" value={progress.current_trades} />
            <Statistic
              title="AI 深度分析"
              value={aiCallCount}
              suffix="次"
              valueStyle={{ color: '#1677ff' }}
            />
            {currentEquity > 0 && (
              <Statistic
                title="当前权益"
                value={currentEquity}
                precision={2}
                suffix={`(${equityChangePct}%)`}
                valueStyle={{
                  color: equityChange >= 0 ? '#52c41a' : '#ff4d4f',
                }}
              />
            )}
          </Space>
        </div>

        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Text type="secondary">{progress.message}</Text>
        </div>

        {/* 终止按钮 */}
        {isRunning && onStop && (
          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <Button
              danger
              icon={<StopOutlined />}
              onClick={onStop}
              loading={isStopping}
              disabled={isStopping}
            >
              {isStopping ? '正在终止...' : '终止回测'}
            </Button>
          </div>
        )}
      </Card>

      {/* 技术指标 */}
      {progress.indicators && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space wrap>
            <Text strong>技术指标: </Text>
            <Text>MA5: {progress.indicators.ma5?.toFixed(2) || '-'}</Text>
            <Text>MA10: {progress.indicators.ma10?.toFixed(2) || '-'}</Text>
            <Text>EMA20: {progress.indicators.ema20?.toFixed(2) || '-'}</Text>
            <Text>EMA50: {progress.indicators.ema50?.toFixed(2) || '-'}</Text>
            <Text>RSI14: {progress.indicators.rsi_14?.toFixed(1) || '-'}</Text>
            <Text>VolMA20: {progress.indicators.volume_ma20 ? (progress.indicators.volume_ma20 / 1000).toFixed(0) + 'K' : '-'}</Text>
          </Space>
        </Card>
      )}

      {/* 初始分析信息 */}
      {progress.initial_analysis && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space wrap>
            <Text strong>初始分析: </Text>
            <Tag color={TREND_MAP[progress.initial_analysis.trend]?.color || 'default'}>
              {TREND_MAP[progress.initial_analysis.trend]?.label || progress.initial_analysis.trend}
            </Tag>
            {progress.initial_analysis.trend_summary && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {progress.initial_analysis.trend_summary}
              </Text>
            )}
          </Space>
        </Card>
      )}

      {/* 关键位展示 */}
      {progress.key_levels && progress.key_levels.length > 0 && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space wrap>
            <Text strong>关键位: </Text>
            {progress.key_levels.map((level: KeyLevel, idx: number) => (
              <Tag key={idx} color={level.type === 'support' ? 'cyan' : 'magenta'}>
                {level.type === 'support' ? '支撑' : '阻力'} {level.price.toFixed(2)}
                {level.distance_pct != null && ` (${level.distance_pct.toFixed(2)}%)`}
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      {/* 当前价格 */}
      {progress.close_price != null && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space>
            <Text strong>当前价格: </Text>
            <Text style={{ fontSize: 18, fontWeight: 700, color: '#1677ff' }}>
              {progress.close_price.toFixed(2)}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              （最新K线收盘价）
            </Text>
          </Space>
        </Card>
      )}

      {/* 持仓暂停指示 */}
      {progress.has_position && (
        <Alert
          style={{ marginBottom: 16 }}
          type="info"
          showIcon
          message={
            <Space>
              <Text strong>AI 分析已暂停</Text>
              {progress.current_position?.direction && (
                <Tag color={progress.current_position.direction === 'long' ? 'red' : 'green'}>
                  {progress.current_position.direction === 'long' ? '多头持仓' : '空头持仓'}
                </Tag>
              )}
            </Space>
          }
          description="持仓期间暂停 AI 分析，平仓后自动恢复"
        />
      )}

      {/* AI 分析触发原因 */}
      {progress.trigger_reason && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space>
            <Text strong>触发原因: </Text>
            <Tag color={TRIGGER_REASON_MAP[progress.trigger_reason]?.color || 'default'}>
              {TRIGGER_REASON_MAP[progress.trigger_reason]?.label || progress.trigger_reason}
            </Tag>
          </Space>
        </Card>
      )}

      {/* AI 分析窗口信息 */}
      {progress.analysis_window && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space wrap>
            <Text strong>分析窗口: </Text>
            <Text>
              K 线范围: {progress.analysis_window.start} - {progress.analysis_window.end}
            </Text>
            <Text>窗口大小: {progress.analysis_window.size} 根</Text>
          </Space>
        </Card>
      )}

      {/* 当前持仓详情 */}
      {progress.has_position && progress.current_position && (
        <Card size="small" title="当前持仓详情" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={4}>
              <Statistic
                title="方向"
                value={progress.current_position.direction === 'long' ? '多头' : '空头'}
                valueStyle={{
                  color: progress.current_position.direction === 'long' ? '#ff4d4f' : '#52c41a',
                }}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="开仓价"
                value={progress.current_position.entry_price ?? 0}
                precision={2}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="数量"
                value={progress.current_position.quantity ?? 0}
                precision={4}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="止损价"
                value={progress.current_position.stop_loss ?? 0}
                precision={2}
                valueStyle={{ color: '#ff4d4f' }}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="止盈价"
                value={progress.current_position.take_profit ?? 0}
                precision={2}
                valueStyle={{ color: '#52c41a' }}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="未实现盈亏"
                value={progress.current_position.unrealized_pnl ?? 0}
                precision={2}
                valueStyle={{
                  color:
                    (progress.current_position.unrealized_pnl || 0) >= 0 ? '#52c41a' : '#ff4d4f',
                }}
              />
            </Col>
          </Row>
        </Card>
      )}

      {/* AI 实时分析面板（增强版） */}
      {aiAnalysis && (
        <Card title="AI 实时分析" style={{ marginBottom: 16 }}>
          <Row gutter={[16, 12]}>
            <Col span={12}>
              <Space>
                <Text type="secondary">市场趋势:</Text>
                <Tag color={TREND_MAP[aiAnalysis.trend]?.color || 'default'}>
                  {TREND_MAP[aiAnalysis.trend]?.label || aiAnalysis.trend}
                </Tag>
              </Space>
            </Col>
            <Col span={12}>
              <Space>
                <Text type="secondary">建议决策:</Text>
                <Tag color={DECISION_MAP[aiAnalysis.decision]?.color || 'default'}>
                  {DECISION_MAP[aiAnalysis.decision]?.label || aiAnalysis.decision}
                </Tag>
              </Space>
            </Col>
          </Row>

          <div style={{ marginTop: 12 }}>
            <Space>
              <Text type="secondary">趋势强度:</Text>
              <Rate disabled count={5} value={aiAnalysis.strength} style={{ fontSize: 14 }} />
            </Space>
          </div>

          <div style={{ marginTop: 8 }}>
            <Space>
              <Text type="secondary">置信度:</Text>
              <Rate disabled count={5} value={aiAnalysis.confidence} style={{ fontSize: 14 }} />
            </Space>
          </div>

          {/* 触发策略来源 */}
          {aiAnalysis.source_strategy && (
            <div style={{ marginTop: 12 }}>
              <Space>
                <Text type="secondary">触发策略:</Text>
                <Tag color="blue" style={{ fontSize: 13, fontWeight: 600 }}>
                  {aiAnalysis.source_strategy}
                </Tag>
              </Space>
            </div>
          )}

          {/* 分析摘要 */}
          <div style={{ marginTop: 12 }}>
            <Text type="secondary">分析摘要:</Text>
            <Paragraph
              style={{
                background: '#f5f5f5',
                padding: 12,
                borderRadius: 4,
                fontSize: 12,
                whiteSpace: 'pre-wrap',
                margin: '8px 0 0 0',
                borderLeft: '3px solid #1677ff',
              }}
            >
              {aiAnalysis.summary}
            </Paragraph>
          </div>

          {/* 各策略决策理由 */}
          {aiAnalysis.reason && (
            <div style={{ marginTop: 16, borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
              <Text type="secondary" style={{ fontSize: 13, fontWeight: 600 }}>
                各策略判断：
              </Text>
              <div
                style={{
                  background: '#fffbe6',
                  padding: 12,
                  borderRadius: 4,
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                  margin: '8px 0 0 0',
                  borderLeft: '3px solid #faad14',
                  lineHeight: 2,
                }}
              >
                {aiAnalysis.reason.split('\n').map((line, i) => {
                  // 区分满足/不满足的策略行
                  const isSatisfied = line.includes('满足') && !line.includes('不满足');
                  const isNotSatisfied = line.includes('不满足');
                  return (
                    <div key={i} style={{ color: isNotSatisfied ? '#999' : 'inherit' }}>
                      {isSatisfied && <span style={{ color: '#52c41a', marginRight: 4 }}>✓</span>}
                      {isNotSatisfied && <span style={{ color: '#ff4d4f', marginRight: 4 }}>✗</span>}
                      {line}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};
