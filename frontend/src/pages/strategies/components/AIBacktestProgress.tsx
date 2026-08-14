import React from 'react';
import { Card, Progress, Space, Typography, Spin, Tag, Statistic } from 'antd';
import type { AIBacktestProgress as AIBacktestProgressType } from '@/types/ai-backtest';

const { Text, Title } = Typography;

const STAGE_LABEL: Record<string, string> = {
  preheat: '预热数据获取',
  running: '逐根推进中',
  summary: '生成总结报告',
  done: '完成',
  error: '失败',
};

interface Props {
  progress: AIBacktestProgressType | null;
}

export const AIBacktestProgress: React.FC<Props> = ({ progress }) => {
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
  const stageColor = isError ? 'red' : isDone ? 'green' : 'blue';

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 24 }}>
      <Title level={4} style={{ textAlign: 'center' }}>
        AI 回测进度
      </Title>

      <Card>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Tag color={stageColor}>
            {STAGE_LABEL[progress.stage] || progress.stage}
          </Tag>
        </div>

        <Progress
          percent={Math.round(progress.progress)}
          status={isError ? 'exception' : 'active'}
          strokeColor={{
            '0%': '#1677ff',
            '100%': isDone ? '#52c41a' : '#1677ff',
          }}
          size="large"
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
                  color: (progress.current_position.unrealized_pnl || 0) >= 0 ? '#52c41a' : '#ff4d4f',
                }}
              />
            )}
          </Space>
        </div>

        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Text type="secondary">{progress.message}</Text>
        </div>
      </Card>
    </div>
  );
};