import React, { useState, useCallback } from 'react';
import { Tabs, Card, message } from 'antd';
import dayjs from 'dayjs';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiBacktestApi } from '@/api/ai-backtest';
import { strategyApi } from '@/api/strategies';
import { useSSE } from '@/hooks/useSSE';
import type {
  AIBacktestConfig,
  AIBacktestProgress,
  AIBacktestAIAnalysis,
  AIBacktestAnalysisResult,
  MergeOptimizeRequest,
} from '@/types/ai-backtest';
import { AIBacktestConfigForm } from './AIBacktestConfigForm';
import { AIBacktestProgress as AIBacktestProgressComp } from './AIBacktestProgress';
import { AIBacktestResult } from './AIBacktestResult';
import { AIBacktestHistory } from './AIBacktestHistory';
import { AIBacktestAnalysis } from './AIBacktestAnalysis';
import { MergeOptimizeModal } from './MergeOptimizeModal';

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
  backtestMode: 'single',
  strategyIds: [],
  useLocalModel: false,
  localModelKlines: 10,
  promptTemplateIds: {},
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
  const [aiAnalysis, setAIAnalysis] = useState<AIBacktestAIAnalysis | null>(null);
  const [activeTab, setActiveTab] = useState('config');
  const [tradePage, setTradePage] = useState(1);

  // 分析状态
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [backtestAnalysis, setBacktestAnalysis] = useState<AIBacktestAnalysisResult | null>(null);

  // 终止状态
  const [isStopping, setIsStopping] = useState(false);

  // 融合优化弹窗
  const [mergeModalOpen, setMergeModalOpen] = useState(false);

  // 创建单策略回测
  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof aiBacktestApi.create>[0]) => aiBacktestApi.create(data),
    onSuccess: (res) => {
      const btId = res.data.id;
      setCurrentBacktestId(btId);
      setIsRunning(true);
      setAIAnalysis(null);
      setProgress(null);
      setBacktestAnalysis(null);
      setActiveTab('progress');
    },
    onError: (err: any) => {
      message.error('创建回测失败: ' + (err?.message || '未知错误'));
    },
  });

  // 创建多策略回测
  const createMultiMutation = useMutation({
    mutationFn: (data: Parameters<typeof aiBacktestApi.createMulti>[0]) => aiBacktestApi.createMulti(data),
    onSuccess: (res) => {
      setCurrentBacktestId(res.data.backtests[0].id);
      setIsRunning(true);
      setAIAnalysis(null);
      setProgress(null);
      setBacktestAnalysis(null);
      setActiveTab('progress');
    },
    onError: (err: any) => {
      message.error('创建多策略回测失败: ' + (err?.message || '未知错误'));
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

  // 终止回测
  const stopMutation = useMutation({
    mutationFn: (id: string) => aiBacktestApi.stop(id),
    onSuccess: () => {
      setIsStopping(true);
      message.info('正在终止回测...');
    },
    onError: (err: any) => {
      setIsStopping(false);
      message.error('终止回测失败: ' + (err?.message || '未知错误'));
    },
  });

  // AI 分析
  const analyzeMutation = useMutation({
    mutationFn: (id: string) => aiBacktestApi.analyze(id),
    onSuccess: (res) => {
      setBacktestAnalysis(res.data);
      message.success('AI 分析完成');
      queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'detail', currentBacktestId] });
    },
    onError: (err: any) => {
      message.error('AI 分析失败: ' + (err?.message || '未知错误'));
    },
    onSettled: () => {
      setIsAnalyzing(false);
    },
  });

  // 策略优化
  const optimizeMutation = useMutation({
    mutationFn: (id: string) => aiBacktestApi.optimize(id),
    onSuccess: (res) => {
      message.success('优化策略已生成: ' + res.data.name);
      queryClient.invalidateQueries({ queryKey: ['strategies', 'list'] });
    },
    onError: (err: any) => {
      message.error('策略优化失败: ' + (err?.message || '未知错误'));
    },
    onSettled: () => {
      setIsOptimizing(false);
    },
  });

  // 多策略融合优化
  const mergeOptimizeMutation = useMutation({
    mutationFn: (data: MergeOptimizeRequest) => aiBacktestApi.mergeOptimize(data),
    onSuccess: () => {
      message.success('策略融合优化完成');
      queryClient.invalidateQueries({ queryKey: ['strategies', 'list'] });
      setMergeModalOpen(false);
    },
    onError: (err: any) => {
      message.error('融合优化失败: ' + (err?.message || '未知错误'));
    },
  });

  const handleSSEMessage = useCallback((data: any) => {
    setProgress(data);
    // 提取 AI 分析数据
    if (data.ai_analysis) {
      setAIAnalysis(data.ai_analysis);
    }
  }, []);

  const handleSSEDone = useCallback(() => {
    setIsRunning(false);
    setIsStopping(false);
    queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'detail', currentBacktestId] });
    queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'trades', currentBacktestId] });
    queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'history'] });
  }, [queryClient, currentBacktestId]);

  const handleSSEError = useCallback(() => {
    setIsRunning(false);
    setIsStopping(false);
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
    const promptTemplateIds = config.promptTemplateIds
      ? Object.fromEntries(
          Object.entries(config.promptTemplateIds).filter(([, v]) => v !== null),
        )
      : undefined;

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
      use_local_model: config.useLocalModel,
      local_model_klines: config.localModelKlines,
      prompt_template_ids: promptTemplateIds,
    };

    if (config.backtestMode === 'multi' && config.strategyIds && config.strategyIds.length > 0) {
      createMultiMutation.mutate({ ...payload, strategy_ids: config.strategyIds });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleStop = () => {
    if (currentBacktestId) {
      stopMutation.mutate(currentBacktestId);
    }
  };

  const handleAnalyze = () => {
    if (currentBacktestId) {
      setIsAnalyzing(true);
      analyzeMutation.mutate(currentBacktestId);
    }
  };

  const handleOptimize = () => {
    if (currentBacktestId) {
      setIsOptimizing(true);
      optimizeMutation.mutate(currentBacktestId);
    }
  };

  const handleSelectHistory = (id: string) => {
    setCurrentBacktestId(id);
    setActiveTab('result');
    setBacktestAnalysis(null);
  };

  // 获取当前详情中的 AI 分析结果
  const currentDetail = detailQuery.data?.data;
  const summaryAnalysis = currentDetail?.result_summary?.ai_analysis as AIBacktestAnalysisResult | undefined;
  const displayAnalysis = backtestAnalysis || summaryAnalysis || null;

  const isDetailCompleted = currentDetail?.status === 'completed';
  const isDetailCancelled = currentDetail?.status === 'cancelled';

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
                loading={createMutation.isPending || createMultiMutation.isPending}
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
              <AIBacktestProgressComp
                progress={progress}
                aiAnalysis={aiAnalysis}
                isStopping={isStopping}
                onStop={handleStop}
              />
            ),
          },
          {
            key: 'result',
            label: '结果',
            disabled: !currentBacktestId || isRunning,
            children: (
              <AIBacktestResult
                detail={currentDetail}
                trades={tradesQuery.data?.data?.items || []}
                tradeTotal={tradesQuery.data?.data?.total || 0}
                page={tradePage}
                onPageChange={setTradePage}
                onAnalyze={isDetailCompleted ? handleAnalyze : undefined}
                onMergeOptimize={() => setMergeModalOpen(true)}
              />
            ),
          },
          {
            key: 'analysis',
            label: 'AI 分析',
            disabled: !currentBacktestId || isRunning || (!isDetailCompleted && !isDetailCancelled),
            children: (
              <AIBacktestAnalysis
                backtestId={currentBacktestId!}
                analysis={displayAnalysis}
                isAnalyzing={isAnalyzing}
                onAnalyze={handleAnalyze}
                onOptimize={handleOptimize}
                isOptimizing={isOptimizing}
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
      <MergeOptimizeModal open={mergeModalOpen} onClose={() => setMergeModalOpen(false)} />
    </Card>
  );
};

export default AIBacktestPanel;
