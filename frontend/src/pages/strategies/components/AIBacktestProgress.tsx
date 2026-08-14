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
} from 'antd';
import { StopOutlined } from '@ant-design/icons';
import type {
  AIBacktestProgress as AIBacktestProgressType,
  AIBacktestAIAnalysis,
} from '@/types/ai-backtest';

const { Text, Title, Paragraph } = Typography;

const STAGE_LABEL: Record<string, string> = {
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
            {progress.current_position?.has_position && (
              <Statistic
                title="当前持仓"
                value={progress.current_position.direction === 'long' ? '多头' : '空头'}
                valueStyle={{
                  color:
                    (progress.current_position.unrealized_pnl || 0) >= 0 ? '#52c41a' : '#ff4d4f',
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
          <Space>
            <Text strong>技术指标: </Text>
            <Text>MA5: {progress.indicators.ma5?.toFixed(2) || '-'}</Text>
            <Text>MA10: {progress.indicators.ma10?.toFixed(2) || '-'}</Text>
            <Text>RSI14: {progress.indicators.rsi_14?.toFixed(1) || '-'}</Text>
          </Space>
        </Card>
      )}

      {/* AI 实时分析面板 */}
      {aiAnalysis && (
        <Card title="AI 实时分析" style={{ marginBottom: 16 }}>
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="市场趋势">
              <Tag color={TREND_MAP[aiAnalysis.trend]?.color || 'default'}>
                {TREND_MAP[aiAnalysis.trend]?.label || aiAnalysis.trend}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="趋势强度">
              {'★'.repeat(aiAnalysis.strength)}
              {'☆'.repeat(5 - aiAnalysis.strength)}
            </Descriptions.Item>
            <Descriptions.Item label="建议决策" span={2}>
              <Tag color={DECISION_MAP[aiAnalysis.decision]?.color || 'default'}>
                {DECISION_MAP[aiAnalysis.decision]?.label || aiAnalysis.decision}
              </Tag>
              <Text style={{ marginLeft: 8 }}>
                置信度: {'★'.repeat(aiAnalysis.confidence)}
                {'☆'.repeat(5 - aiAnalysis.confidence)}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="分析摘要" span={2}>
              <Paragraph
                style={{
                  background: '#f5f5f5',
                  padding: 8,
                  borderRadius: 4,
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                  margin: 0,
                }}
              >
                {aiAnalysis.summary}
              </Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="决策理由" span={2}>
              <Text>{aiAnalysis.reason || '-'}</Text>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </div>
  );
};