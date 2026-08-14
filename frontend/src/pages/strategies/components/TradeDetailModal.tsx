import React from 'react';
import { Modal, Descriptions, Typography, Tag, Divider } from 'antd';
import dayjs from 'dayjs';
import type { AIBacktestTrade } from '@/types/ai-backtest';

const { Text, Title, Paragraph } = Typography;

interface Props {
  open: boolean;
  trade: AIBacktestTrade | null;
  onClose: () => void;
}

export const TradeDetailModal: React.FC<Props> = ({ open, trade, onClose }) => {
  if (!trade) return null;

  const isProfitable = (trade.pnl || 0) >= 0;

  return (
    <Modal
      title={`交易 #${trade.index} 详情`}
      open={open}
      onCancel={onClose}
      width={700}
      footer={null}
    >
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label="方向">
          <Tag color={trade.direction === 'long' ? 'red' : 'green'}>
            {trade.direction === 'long' ? '做多' : '做空'}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="盈亏">
          <Text style={{ color: isProfitable ? '#52c41a' : '#ff4d4f', fontSize: 16, fontWeight: 'bold' }}>
            {trade.pnl && trade.pnl >= 0 ? '+' : ''}{trade.pnl?.toFixed(2)} USDT
            {trade.pnl_pct != null ? ` (${trade.pnl_pct.toFixed(2)}%)` : ''}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label="开仓时间">
          {dayjs(trade.entry_time).format('YYYY-MM-DD HH:mm')}
        </Descriptions.Item>
        <Descriptions.Item label="平仓时间">
          {trade.exit_time ? dayjs(trade.exit_time).format('YYYY-MM-DD HH:mm') : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="开仓价">
          {trade.entry_price?.toFixed(4)}
        </Descriptions.Item>
        <Descriptions.Item label="平仓价">
          {trade.exit_price?.toFixed(4) || '-'}
        </Descriptions.Item>
        <Descriptions.Item label="数量">
          {trade.quantity?.toFixed(6)}
        </Descriptions.Item>
        <Descriptions.Item label="持仓 K 线数">
          {trade.holding_bars || '-'}
        </Descriptions.Item>
        <Descriptions.Item label="止损价">
          {trade.stop_loss?.toFixed(4) || '-'}
        </Descriptions.Item>
        <Descriptions.Item label="止盈价">
          {trade.take_profit?.toFixed(4) || '-'}
        </Descriptions.Item>
        <Descriptions.Item label="平仓原因" span={2}>
          {trade.exit_reason || '-'}
        </Descriptions.Item>
        <Descriptions.Item label="置信度">
          {trade.open_confidence ? '★'.repeat(trade.open_confidence) : '-'}
        </Descriptions.Item>
      </Descriptions>

      <Divider />

      {trade.open_ai_analysis && (
        <>
          <Title level={5}>开仓时 AI 分析</Title>
          <Paragraph
            style={{
              background: '#f5f5f5',
              padding: 12,
              borderRadius: 6,
              fontSize: 13,
              whiteSpace: 'pre-wrap',
            }}
          >
            {(() => {
              try {
                const parsed = JSON.parse(trade.open_ai_analysis);
                return parsed.market_analysis?.summary || JSON.stringify(parsed, null, 2);
              } catch {
                return trade.open_ai_analysis!;
              }
            })()}
          </Paragraph>
        </>
      )}

      {trade.open_reason && (
        <>
          <Title level={5}>开仓理由</Title>
          <Paragraph>{trade.open_reason}</Paragraph>
        </>
      )}

      {trade.exit_ai_analysis && (
        <>
          <Divider />
          <Title level={5}>平仓时 AI 分析</Title>
          <Paragraph
            style={{
              background: '#f5f5f5',
              padding: 12,
              borderRadius: 6,
              fontSize: 13,
              whiteSpace: 'pre-wrap',
            }}
          >
            {(() => {
              try {
                const parsed = JSON.parse(trade.exit_ai_analysis);
                return parsed.market_analysis?.summary || JSON.stringify(parsed, null, 2);
              } catch {
                return trade.exit_ai_analysis!;
              }
            })()}
          </Paragraph>
        </>
      )}
    </Modal>
  );
};