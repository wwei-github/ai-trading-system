import React from 'react';
import {
  Card, Button, Typography, Spin, Empty, Space, Tag, Divider, Alert,
} from 'antd';
import {
  ThunderboltOutlined, RobotOutlined, FileAddOutlined,
} from '@ant-design/icons';
import type { AIBacktestAnalysisResult } from '@/types/ai-backtest';

const { Title, Text, Paragraph } = Typography;

interface Props {
  backtestId: string;
  analysis: AIBacktestAnalysisResult | null;
  isAnalyzing: boolean;
  onAnalyze: () => void;
  onOptimize: () => void;
  isOptimizing: boolean;
}

const MARKET_LABELS: Record<string, string> = {
  trend_market: '趋势市场',
  range_market: '震荡市场',
  volatile_market: '高波动市场',
};

const LEVEL_COLORS: Record<string, string> = {
  优秀: 'success',
  良好: 'processing',
  一般: 'warning',
  较差: 'error',
};

export const AIBacktestAnalysis: React.FC<Props> = ({
  analysis, isAnalyzing, onAnalyze, onOptimize, isOptimizing,
}) => {
  return (
    <div>
      {/* 操作按钮 */}
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<RobotOutlined />}
            onClick={onAnalyze}
            loading={isAnalyzing}
            disabled={isAnalyzing}
          >
            AI 分析回测结果
          </Button>
          <Button
            icon={<FileAddOutlined />}
            onClick={onOptimize}
            loading={isOptimizing}
            disabled={!analysis || isOptimizing}
          >
            生成优化策略
          </Button>
          {!analysis && (
            <Text type="secondary">请先进行 AI 分析，再生成优化策略</Text>
          )}
        </Space>
      </Card>

      {/* 分析结果 */}
      {isAnalyzing ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" tip="AI 正在分析回测结果..." />
        </div>
      ) : analysis ? (
        <Card>
          {/* 综合评分 */}
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <Title level={3}>
              综合评分:{' '}
              <Text
                type={
                  analysis.score >= 70
                    ? 'success'
                    : analysis.score >= 40
                    ? 'warning'
                    : 'danger'
                }
              >
                {analysis.score}/100
              </Text>
            </Title>
          </div>

          {/* 整体评估 */}
          <Card size="small" style={{ marginBottom: 16, background: '#f6f8fa' }}>
            <Paragraph style={{ margin: 0 }}>{analysis.overall_assessment}</Paragraph>
          </Card>

          {/* 优势与不足 */}
          <Space style={{ width: '100%' }} size={16}>
            <Card size="small" title="优势" style={{ flex: 1 }}>
              {analysis.strengths?.map((s: string, i: number) => (
                <Text key={i} style={{ display: 'block', marginBottom: 4 }}>
                  ✅ {s}
                </Text>
              ))}
              {(!analysis.strengths || analysis.strengths.length === 0) && (
                <Text type="secondary">暂无数据</Text>
              )}
            </Card>
            <Card size="small" title="不足" style={{ flex: 1 }}>
              {analysis.weaknesses?.map((w: string, i: number) => (
                <Text key={i} style={{ display: 'block', marginBottom: 4 }}>
                  ⚠️ {w}
                </Text>
              ))}
              {(!analysis.weaknesses || analysis.weaknesses.length === 0) && (
                <Text type="secondary">暂无数据</Text>
              )}
            </Card>
          </Space>

          <Divider />

          {/* 市场适应性 */}
          <Card size="small" title="市场适应性" style={{ marginBottom: 16 }}>
            {Object.entries(analysis.market_adaptability || {}).map(([market, level]) => (
              <div key={market} style={{ marginBottom: 8 }}>
                <Text strong>{MARKET_LABELS[market] || market}:</Text>
                <Tag
                  color={LEVEL_COLORS[level] || 'default'}
                  style={{ marginLeft: 8 }}
                >
                  {level}
                </Tag>
              </div>
            ))}
          </Card>

          {/* 改进建议 */}
          <Card size="small" title="改进建议">
            {analysis.improvement_suggestions?.map((s: string, i: number) => (
              <Alert
                key={i}
                message={`建议 ${i + 1}`}
                description={s}
                type="info"
                showIcon
                style={{ marginBottom: 8 }}
              />
            ))}
            {(!analysis.improvement_suggestions ||
              analysis.improvement_suggestions.length === 0) && (
              <Text type="secondary">暂无建议</Text>
            )}
          </Card>
        </Card>
      ) : (
        <Empty description="点击上方按钮开始 AI 分析" />
      )}
    </div>
  );
};