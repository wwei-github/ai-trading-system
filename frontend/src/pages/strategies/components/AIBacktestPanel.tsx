import React, { useState, useCallback } from 'react';
import { Tabs, Card, message } from 'antd';
import dayjs from 'dayjs';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiBacktestApi } from '@/api/ai-backtest';
import { strategyApi } from '@/api/strategies';
import { useSSE } from '@/hooks/useSSE';
import type { AIBacktestConfig, AIBacktestProgress } from '@/types/ai-backtest';
import { AIBacktestConfigForm } from './AIBacktestConfigForm';
import { AIBacktestProgress as AIBacktestProgressComp } from './AIBacktestProgress';
import { AIBacktestResult } from './AIBacktestResult';
import { AIBacktestHistory } from './AIBacktestHistory';

const DEFAULT_CONFIG: AIBacktestConfig = {
  strategyId: '',
  symbol: 'BTC/USDT',
  timeframe: '15m',
  startDate: dayjs().subtract(30, 'day').toISOString(),
  mode: 'kline_count',
  klineCount: 500,
  timeSpanValue: 7,
  timeSpanUnit: 'day',
  initialCapital: 10000,
  feeRate: 0.001,
  useAI: true,
  prerequisites: {
    single_position: { enabled: true, description: '单仓规则：同时只持有一个仓位' },
    mandatory_stop_loss: { enabled: true, default_stop_loss_pct: 3, description: '强制止损：每笔开仓必须设置止损' },
    strict_execution: { enabled: true, description: '严格执规：AI 决策必须遵循策略规则' },
  },
};

interface Props {
  strategyId: string;
}

const AIBacktestPanel: React.FC<Props> = ({ strategyId }) => {
  const queryClient = useQueryClient();
  const [config, setConfig] = useState<AIBacktestConfig>({
    ...DEFAULT_CONFIG,
    strategyId,
  });

  // 获取策略列表
  const { data: strategies } = useQuery({
    queryKey: ['strategies', 'list'],
    queryFn: () => strategyApi.getList(),
  });
  const strategyOptions = (strategies || []).map((s: any) => ({ id: s.id, name: s.name }));

  const [currentBacktestId, setCurrentBacktestId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState<AIBacktestProgress | null>(null);
  const [activeTab, setActiveTab] = useState('config');
  const [tradePage, setTradePage] = useState(1);

  // 创建回测
  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof aiBacktestApi.create>[0]) => aiBacktestApi.create(data),
    onSuccess: (res) => {
      const btId = res.data.id;
      setCurrentBacktestId(btId);
      setIsRunning(true);
      setActiveTab('progress');
    },
    onError: (err: any) => {
      message.error('创建回测失败: ' + (err?.message || '未知错误'));
    },
  });

  // 回测详情
  const detailQuery = useQuery({
    queryKey: ['ai-backtest', 'detail', currentBacktestId],
    queryFn: () => aiBacktestApi.getDetail(currentBacktestId!),
    enabled: !!currentBacktestId && !isRunning,
  });

  // 交易明细
  const tradesQuery = useQuery({
    queryKey: ['ai-backtest', 'trades', currentBacktestId, tradePage],
    queryFn: () => aiBacktestApi.getTrades(currentBacktestId!, tradePage),
    enabled: !!currentBacktestId && !isRunning,
  });

  const handleSSEMessage = useCallback((data: any) => {
    setProgress(data);
  }, []);

  const handleSSEDone = useCallback(() => {
    setIsRunning(false);
    queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'detail', currentBacktestId] });
    queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'trades', currentBacktestId] });
    queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'history'] });
  }, [queryClient, currentBacktestId]);

  const handleSSEError = useCallback(() => {
    setIsRunning(false);
    message.warning('进度连接中断，请刷新页面查看最新状态');
  }, []);

  useSSE({
    url: currentBacktestId ? aiBacktestApi.getProgressUrl(currentBacktestId) : '',
    enabled: isRunning && !!currentBacktestId,
    onMessage: handleSSEMessage,
    onDone: handleSSEDone,
    onError: handleSSEError,
  });

  const handleStart = () => {
    const payload = {
      strategy_id: config.strategyId,
      symbol: config.symbol,
      timeframe: config.timeframe,
      start_time: config.startDate,
      mode: config.mode,
      kline_count: config.mode === 'kline_count' ? config.klineCount : undefined,
      time_span_value: config.mode === 'time_span' ? config.timeSpanValue : undefined,
      time_span_unit: config.mode === 'time_span' ? config.timeSpanUnit : undefined,
      initial_capital: config.initialCapital,
      fee_rate: config.feeRate,
      use_ai: config.useAI,
      prerequisites: config.prerequisites,
    };
    createMutation.mutate(payload);
  };

  const handleSelectHistory = (id: string) => {
    setCurrentBacktestId(id);
    setActiveTab('result');
  };

  return (
    <Card>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'config',
            label: '配置',
            children: (
              <AIBacktestConfigForm
                config={config}
                onChange={setConfig}
                onSubmit={handleStart}
                loading={createMutation.isPending}
                disabled={isRunning}
                strategies={strategyOptions}
              />
            ),
          },
          {
            key: 'progress',
            label: '进度',
            disabled: !isRunning,
            children: (
              <AIBacktestProgressComp progress={progress} />
            ),
          },
          {
            key: 'result',
            label: '结果',
            disabled: !currentBacktestId || isRunning,
            children: (
              <AIBacktestResult
                detail={detailQuery.data?.data}
                trades={tradesQuery.data?.data?.items || []}
                tradeTotal={tradesQuery.data?.data?.total || 0}
                page={tradePage}
                onPageChange={setTradePage}
              />
            ),
          },
          {
            key: 'history',
            label: '历史',
            children: (
              <AIBacktestHistory
                onSelect={handleSelectHistory}
              />
            ),
          },
        ]}
      />
    </Card>
  );
};

export default AIBacktestPanel;