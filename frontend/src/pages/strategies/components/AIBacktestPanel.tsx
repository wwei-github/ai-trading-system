import React, { useState, useCallback, useEffect } from 'react';
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
} from '@/types/ai-backtest';
import { AIBacktestConfigForm } from './AIBacktestConfigForm';
import { AIBacktestProgress as AIBacktestProgressComp } from './AIBacktestProgress';
import { AIBacktestResult } from './AIBacktestResult';
import { AIBacktestHistory } from './AIBacktestHistory';
import { AIBacktestAnalysis } from './AIBacktestAnalysis';

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

// localStorage 持久化 key
const LS_BACKTEST_ID = 'ai_backtest_current_id';

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

  // 从 localStorage 恢复回测 ID
  const [currentBacktestId, setCurrentBacktestId] = useState<string | null>(
    () => localStorage.getItem(LS_BACKTEST_ID),
  );
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

  // 页面挂载时自动检测 localStorage 中的回测是否仍在运行
  useEffect(() => {
    const savedId = localStorage.getItem(LS_BACKTEST_ID);
    if (!savedId) return;

    // 查询详情，判断状态
    aiBacktestApi.getDetail(savedId).then((res) => {
      const detail = res.data;
      if (detail.status === 'running' || detail.status === 'pending') {
        setCurrentBacktestId(savedId);
        setIsRunning(true);
        setActiveTab('progress');
        message.info('检测到正在进行的回测，已恢复进度显示');
      } else if (detail.status === 'completed' || detail.status === 'cancelled' || detail.status === 'failed') {
        // 已完成，清除 localStorage 并显示结果
        localStorage.removeItem(LS_BACKTEST_ID);
        setCurrentBacktestId(savedId);
        setActiveTab('result');
      }
    }).catch(() => {
      // 回测不存在或出错，清除 localStorage
      localStorage.removeItem(LS_BACKTEST_ID);
    });
  }, []);

  // 创建单策略回测
  const createMutation = useMutation({
    mutationFn: (data: Parameters<typeof aiBacktestApi.create>[0]) => aiBacktestApi.create(data),
    onSuccess: (res) => {
      const btId = res.data.id;
      localStorage.setItem(LS_BACKTEST_ID, btId);
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

  // 创建多策略回测 - 后端 /multi 接口未实现,移除相关逻辑

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

  // 多策略融合优化 - 由 MergeOptimizeModal 内部处理 mutation,无需在此定义

  const handleSSEMessage = useCallback((data: any) => {
    // pending 状态：回测在排队中，通知用户并保持当前页面
    if (data.stage === 'pending') {
      message.info('回测正在排队等待执行，请稍候...');
      return;
    }
    setProgress(data);
    // 提取 AI 分析数据
    if (data.ai_analysis) {
      setAIAnalysis(data.ai_analysis);
    }
  }, []);

  const handleSSEDone = useCallback(() => {
    setIsRunning(false);
    setIsStopping(false);
    localStorage.removeItem(LS_BACKTEST_ID);
    // 如果 progress 的 stage 是 pending，不切换到 result 页
    if (progress?.stage === 'pending') {
      return;
    }
    queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'detail', currentBacktestId] });
    queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'trades', currentBacktestId] });
    queryClient.invalidateQueries({ queryKey: ['ai-backtest', 'history'] });
  }, [queryClient, currentBacktestId, progress?.stage]);

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

    // 后端 /multi 接口未实现,多策略回测暂时禁用,统一走单策略
    if (config.backtestMode === 'multi') {
      message.warning('多策略回测接口暂未实现,请使用单策略回测。融合优化请在历史记录中手动选择已完成回测进行。');
      return;
    }
    createMutation.mutate(payload);
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
    </Card>
  );
};

export default AIBacktestPanel;
