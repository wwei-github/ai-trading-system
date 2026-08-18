import React, { useEffect, useState } from 'react';
import {
  Form, InputNumber, Select, DatePicker, Switch, Button, Space,
  Card, Row, Col, Typography, Divider, Alert, Collapse, Tag, Radio,
  Tooltip,
} from 'antd';
import {
  PlayCircleOutlined,
  SettingOutlined,
  RobotOutlined,
  AppstoreAddOutlined,
  FileTextOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
import type { AIBacktestConfig } from '@/types/ai-backtest';
import { promptTemplateApi } from '@/api/ai-backtest';
import { strategyApi } from '@/api/strategies';

const { Text, Title } = Typography;

// 指标中文名映射
const INDICATOR_NAME_MAP: Record<string, string> = {
  EMA50: 'EMA50',
  EMA20: 'EMA20',
  MA5: 'MA5',
  MA10: 'MA10',
  MA20: 'MA20',
  'Stochastic%D': '随机指标 %D',
  Stochastic: '随机指标',
  stoch_k: '随机指标 %K',
  stoch_d: '随机指标 %D',
  CandlestickPattern: '蜡烛图形态',
  RSI: 'RSI',
  rsi_14: 'RSI(14)',
  MACD: 'MACD',
  BOLL: '布林带',
  ATR: 'ATR',
  Volume: '成交量',
  volume_ma20: '成交量均线',
  StopLoss: '止损',
  TakeProfit: '止盈',
};

// 指标图标颜色（按类别区分）
const INDICATOR_COLOR_MAP: Record<string, string> = {
  EMA50: 'blue',
  EMA20: 'blue',
  MA5: 'blue',
  MA10: 'blue',
  MA20: 'blue',
  'Stochastic%D': 'purple',
  Stochastic: 'purple',
  stoch_k: 'purple',
  stoch_d: 'purple',
  CandlestickPattern: 'orange',
  RSI: 'cyan',
  rsi_14: 'cyan',
  MACD: 'geekblue',
  BOLL: 'green',
  ATR: 'red',
  Volume: 'gold',
  volume_ma20: 'gold',
  StopLoss: 'red',
  TakeProfit: 'green',
};

/** 从策略 rules 中提取所有使用的指标名称 */
function extractIndicatorsFromRules(rules: Record<string, any>): string[] {
  const indicators = new Set<string>();

  const extractFromConditions = (conditions: any[]) => {
    for (const cond of conditions || []) {
      if (cond.indicator) {
        indicators.add(cond.indicator);
      }
    }
  };

  // 从 entry_rules 提取
  const entryRules = rules?.entry_rules || [];
  for (const group of entryRules) {
    extractFromConditions(group.conditions);
  }

  // 从 exit_rules 提取
  const exitRules = rules?.exit_rules || [];
  for (const group of exitRules) {
    extractFromConditions(group.conditions);
  }

  // 兼容旧版 DSL 格式（condition_group 嵌套）
  const entryConditionGroup = rules?.entry?.condition_group;
  if (entryConditionGroup) {
    extractFromConditions(entryConditionGroup.conditions);
  }
  const exitConditionGroup = rules?.exit;
  if (exitConditionGroup) {
    extractFromConditions(exitConditionGroup?.stop_loss?.conditions);
    extractFromConditions(exitConditionGroup?.take_profit?.conditions);
  }

  return Array.from(indicators);
}

interface Props {
  config: AIBacktestConfig;
  onChange: (config: AIBacktestConfig) => void;
  onSubmit: () => void;
  loading: boolean;
  disabled: boolean;
  strategies?: Array<{ id: string; name: string }>;
}

export const AIBacktestConfigForm: React.FC<Props> = ({
  config, onChange, onSubmit, loading, disabled, strategies,
}) => {
  const [form] = Form.useForm();

  // 拉取三类 Prompt 模板选项
  const { data: initialAnalysisRes } = useQuery({
    queryKey: ['promptTemplates', 'initial_analysis'],
    queryFn: () => promptTemplateApi.list({ category: 'initial_analysis', active_only: true }),
  });
  const { data: precheckRes } = useQuery({
    queryKey: ['promptTemplates', 'backtest_precheck'],
    queryFn: () => promptTemplateApi.list({ category: 'backtest_precheck', active_only: true }),
  });
  const { data: deepAnalysisRes } = useQuery({
    queryKey: ['promptTemplates', 'deep_analysis'],
    queryFn: () => promptTemplateApi.list({ category: 'deep_analysis', active_only: true }),
  });

  const initialAnalysisOptions = (initialAnalysisRes?.data?.items || []).map(t => ({
    label: t.name,
    value: t.id,
  }));
  const precheckOptions = (precheckRes?.data?.items || []).map(t => ({
    label: t.name,
    value: t.id,
  }));
  const deepAnalysisOptions = (deepAnalysisRes?.data?.items || []).map(t => ({
    label: t.name,
    value: t.id,
  }));

  const handleSubmit = async () => {
    try {
      await form.validateFields();
      onSubmit();
    } catch {
      // 表单校验失败，antd 会显示错误信息
    }
  };

  const isMulti = config.backtestMode === 'multi';
  const useLocal = config.useLocalModel === true;
  const usePrecheck = config.usePrecheck !== false;

  // 策略匹配的指标列表
  const [strategyIndicators, setStrategyIndicators] = useState<Record<string, string[]>>({});

  // 选中策略时自动提取指标
  useEffect(() => {
    const fetchIndicators = async () => {
      const ids = isMulti
        ? (config.strategyIds || [])
        : (config.strategyId ? [config.strategyId] : []);

      if (ids.length === 0) {
        setStrategyIndicators({});
        return;
      }

      // 只获取新增的或尚未缓存的策略
      const toFetch = ids.filter(id => !strategyIndicators[id]);
      if (toFetch.length === 0 && Object.keys(strategyIndicators).length === ids.length) {
        return; // 全部已缓存
      }

      const result: Record<string, string[]> = { ...strategyIndicators };
      for (const id of toFetch) {
        try {
          const res = await strategyApi.getDetail(id);
          const strategy = res as any;
          const rules = strategy.rules || {};
          result[id] = extractIndicatorsFromRules(rules);
        } catch (e) {
          console.error(`获取策略详情失败: ${id}`, e);
          result[id] = [];
        }
      }
      setStrategyIndicators(result);
    };

    fetchIndicators();
  }, [config.strategyId, config.strategyIds, isMulti]);

  // 获取当前选中策略的指标展示数据
  const currentIndicatorList = (() => {
    const ids = isMulti ? (config.strategyIds || []) : (config.strategyId ? [config.strategyId] : []);
    const result: Array<{ strategyId: string; strategyName: string; indicators: string[] }> = [];
    for (const id of ids) {
      const name = (strategies || []).find(s => s.id === id)?.name || id;
      const indicators = strategyIndicators[id] || [];
      result.push({ strategyId: id, strategyName: name, indicators });
    }
    return result;
  })();

  const prefilterAlertProps = useLocal
    ? {
        type: 'success' as const,
        message: '本地模型预筛模式',
        description:
          '使用本地轻量模型对每根 K 线进行预筛，仅在触发条件时调用主 AI，可显著节省 Token 消耗。预筛 K 线数量决定本地模型分析窗口大小。',
      }
    : {
        type: 'warning' as const,
        message: '主 AI 预筛模式',
        description:
          '每根 K 线都直接调用主 AI 进行分析，无预筛环节，分析更细致但消耗更多 Token。建议在长周期回测时启用本地模型预筛。',
      };

  return (
    <div style={{ maxWidth: 700, margin: '0 auto' }}>
      <Title level={4}>AI 回测配置</Title>
      <Text type="secondary">
        AI 驱动回测将逐根 K 线推进，每根调用 AI 进行市场分析，模拟真实交易决策过程。
      </Text>
      <Divider />

      <Form
        form={form}
        layout="vertical"
        initialValues={{
          strategyId: config.strategyId,
          symbol: config.symbol,
          timeframe: config.timeframe,
          startDate: dayjs(config.startDate),
          mode: config.mode,
          klineCount: config.klineCount,
          timeSpanValue: config.timeSpanValue,
          timeSpanUnit: config.timeSpanUnit,
          initialCapital: config.initialCapital,
          feeRate: config.feeRate,
          useAI: config.useAI,
          prerequisites: {
            single_position: { enabled: config.prerequisites?.single_position?.enabled ?? true },
            mandatory_stop_loss: {
              enabled: config.prerequisites?.mandatory_stop_loss?.enabled ?? true,
              default_stop_loss_pct: config.prerequisites?.mandatory_stop_loss?.default_stop_loss_pct ?? 3,
            },
            strict_execution: { enabled: config.prerequisites?.strict_execution?.enabled ?? true },
          },
          backtestMode: config.backtestMode ?? 'single',
          strategyIds: config.strategyIds ?? [],
          useLocalModel: config.useLocalModel ?? false,
          localModelKlines: config.localModelKlines ?? 10,
          usePrecheck: config.usePrecheck ?? true,
          promptTemplateIds: config.promptTemplateIds ?? {},
        }}
        onValuesChange={(changed, all) => {
          const prerequisites = {
            single_position: {
              enabled: all.prerequisites?.single_position?.enabled ?? true,
              description: '单仓规则：同时只持有一个仓位',
            },
            mandatory_stop_loss: {
              enabled: all.prerequisites?.mandatory_stop_loss?.enabled ?? true,
              default_stop_loss_pct: all.prerequisites?.mandatory_stop_loss?.default_stop_loss_pct ?? 3,
              description: '强制止损：每笔开仓必须设置止损',
            },
            strict_execution: {
              enabled: all.prerequisites?.strict_execution?.enabled ?? true,
              description: '严格执规：AI 决策必须遵循策略规则',
            },
          };
          onChange({
            ...config,
            strategyId: all.strategyId,
            symbol: all.symbol,
            timeframe: all.timeframe,
            startDate: all.startDate?.toISOString() || config.startDate,
            mode: all.mode,
            klineCount: all.klineCount,
            timeSpanValue: all.timeSpanValue,
            timeSpanUnit: all.timeSpanUnit,
            initialCapital: all.initialCapital,
            feeRate: all.feeRate,
            useAI: all.useAI,
            prerequisites,
            backtestMode: all.backtestMode,
            strategyIds: all.strategyIds,
            useLocalModel: all.useLocalModel,
            localModelKlines: all.localModelKlines,
            usePrecheck: all.usePrecheck,
            promptTemplateIds: all.promptTemplateIds,
          });
        }}
        disabled={disabled}
      >
        {/* 回测模式：单策略 / 多策略 */}
        <Form.Item label="回测模式" name="backtestMode" rules={[{ required: true }]}>
          <Radio.Group>
            <Radio value="single">单策略回测</Radio>
            <Radio value="multi">多策略回测</Radio>
          </Radio.Group>
        </Form.Item>

        {/* 策略选择：根据回测模式切换 */}
        {isMulti ? (
          <Card size="small" style={{ marginBottom: 16 }}>
            <Space align="center" style={{ marginBottom: 12 }}>
              <AppstoreAddOutlined />
              <Text strong>多策略选择（2-5 个）</Text>
            </Space>
            <Form.Item
              label="策略列表"
              name="strategyIds"
              rules={[
                { required: true, message: '请选择策略' },
                {
                  validator: (_, value: string[]) => {
                    if (!value || value.length < 2) {
                      return Promise.reject('至少选择 2 个策略');
                    }
                    if (value.length > 5) {
                      return Promise.reject('最多选择 5 个策略');
                    }
                    return Promise.resolve();
                  },
                },
              ]}
            >
              <Select
                mode="multiple"
                allowClear
                placeholder="请选择 2-5 个策略"
                showSearch
                optionFilterProp="label"
                options={(strategies || []).map(s => ({ label: s.name, value: s.id }))}
              />
            </Form.Item>
          </Card>
        ) : (
          <Form.Item label="选择策略" name="strategyId" rules={[{ required: true, message: '请选择策略' }]}>
            <Select
              allowClear
              placeholder="请选择策略"
              showSearch
              optionFilterProp="label"
              options={(strategies || []).map(s => ({ label: s.name, value: s.id }))}
            />
          </Form.Item>
        )}

        {/* 策略匹配指标展示 */}
        {currentIndicatorList.length > 0 && (
          <Card
            size="small"
            style={{ marginBottom: 16, background: '#fafafa' }}
            title={
              <Space>
                <LineChartOutlined />
                <span>策略匹配指标</span>
                <Tag color="green" style={{ marginLeft: 4 }}>
                  已匹配
                </Tag>
              </Space>
            }
          >
            {currentIndicatorList.map(item => (
              <div key={item.strategyId} style={{ marginBottom: item.indicators.length > 0 ? 8 : 0 }}>
                <Text strong style={{ fontSize: 13 }}>{item.strategyName}</Text>
                {item.indicators.length > 0 ? (
                  <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {item.indicators.map(ind => (
                      <Tooltip key={ind} title={`策略条件中使用: ${ind}`}>
                        <Tag
                          color={INDICATOR_COLOR_MAP[ind] || 'default'}
                          style={{ fontSize: 12, padding: '0 8px' }}
                        >
                          {INDICATOR_NAME_MAP[ind] || ind}
                        </Tag>
                      </Tooltip>
                    ))}
                  </div>
                ) : (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    暂未解析到指标信息
                  </Text>
                )}
              </div>
            ))}
          </Card>
        )}

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="交易对" name="symbol" rules={[{ required: true }]}>
              <Select
                options={['BTC/USDT', 'ETH/USDT', 'SOL/USDT'].map(s => ({ label: s, value: s }))}
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="K 线周期" name="timeframe" rules={[{ required: true }]}>
              <Select
                options={[
                  { label: '15 分钟', value: '15m' },
                  { label: '1 小时', value: '1h' },
                  { label: '4 小时', value: '4h' },
                  { label: '1 天', value: '1d' },
                ]}
              />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item label="开始时间" name="startDate" rules={[{ required: true }]}>
          <DatePicker
            showTime
            style={{ width: '100%' }}
            disabledDate={(d) => d && d.isAfter(dayjs())}
          />
        </Form.Item>

        <Form.Item label="回测模式" name="mode" rules={[{ required: true }]}>
          <Select
            options={[
              { label: '按 K 线数量', value: 'kline_count' },
              { label: '按时间跨度', value: 'time_span' },
            ]}
          />
        </Form.Item>

        {config.mode === 'kline_count' ? (
          <Form.Item
            label="K 线数量"
            name="klineCount"
            rules={[{ required: true, type: 'number', min: 1, max: 5000 }]}
          >
            <InputNumber
              min={1}
              max={5000}
              style={{ width: '100%' }}
              addonAfter="根"
            />
          </Form.Item>
        ) : (
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="时间跨度" name="timeSpanValue" rules={[{ required: true }]}>
                <InputNumber min={1} max={365} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="单位" name="timeSpanUnit" rules={[{ required: true }]}>
                <Select
                  options={[
                    { label: '小时', value: 'hour' },
                    { label: '天', value: 'day' },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
        )}

        <Divider />

        <Row gutter={16}>
          <Col span={8}>
            <Form.Item
              label="初始资金 (USDT)"
              name="initialCapital"
              rules={[{ required: true, type: 'number', min: 100 }]}
            >
              <InputNumber min={100} max={100_000_000} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item
              label="手续费率"
              name="feeRate"
              rules={[{ required: true, type: 'number', min: 0, max: 0.01 }]}
            >
              <InputNumber
                min={0}
                max={0.01}
                step={0.0001}
                style={{ width: '100%' }}
              />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="使用 AI 分析" name="useAI" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
        </Row>

        <Divider />

        {/* 预筛开关 */}
        <Form.Item
          label="启用预筛"
          name="usePrecheck"
          valuePropName="checked"
          extra="关闭后每根 K 线都直接拿最新 300 根做深度分析，跳过预筛阶段"
          tooltip="开启：先通过预筛（本地模型或主AI）筛选，再决定是否深度分析\n关闭：每根 K 线都直接使用最新 300 根 K 线进行深度分析"
        >
          <Switch />
        </Form.Item>

        {usePrecheck && (
          /* 本地模型预筛配置 */
          <Card
            size="small"
            title={
              <Space>
                <RobotOutlined />
                <span>本地模型预筛配置</span>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label="预筛模式"
                  name="useLocalModel"
                  valuePropName="checked"
                  extra="本地模型辅助 vs 主AI预筛"
                >
                  <Switch
                    checkedChildren="本地模型"
                    unCheckedChildren="主AI"
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="预筛 K 线数量"
                  name="localModelKlines"
                  rules={[{ type: 'number', min: 1, max: 100 }]}
                  extra="范围 1-100，默认 10"
                >
                  <InputNumber
                    min={1}
                    max={100}
                    defaultValue={10}
                    style={{ width: '100%' }}
                    addonAfter="根"
                  />
                </Form.Item>
              </Col>
            </Row>
            <Alert
              type={prefilterAlertProps.type}
              message={prefilterAlertProps.message}
              description={prefilterAlertProps.description}
              showIcon
            />
          </Card>
        )}

        {/* Prompt 模板选择 */}
        <Collapse
          items={[
            {
              key: 'promptTemplates',
              label: (
                <Space>
                  <FileTextOutlined />
                  <span>Prompt 模板配置</span>
                  <Tag color="purple" style={{ marginLeft: 8 }}>
                    可选
                  </Tag>
                </Space>
              ),
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Form.Item
                    label="初始分析模板"
                    name={['promptTemplateIds', 'initial_analysis']}
                    tooltip="回测启动时对初始 K 线窗口进行的趋势分析 Prompt"
                  >
                    <Select
                      allowClear
                      placeholder="使用默认模板"
                      options={initialAnalysisOptions}
                    />
                  </Form.Item>
                  {usePrecheck && (
                    <Form.Item
                      label="回测预筛模板"
                      name={['promptTemplateIds', 'backtest_precheck']}
                      tooltip="每根 K 线预筛阶段使用的 Prompt（决定是否触发深度分析）"
                    >
                      <Select
                        allowClear
                        placeholder="使用默认模板"
                        options={precheckOptions}
                      />
                    </Form.Item>
                  )}
                  <Form.Item
                    label="深度分析模板"
                    name={['promptTemplateIds', 'deep_analysis']}
                    tooltip="预筛触发后进行的深度 AI 分析 Prompt"
                  >
                    <Select
                      allowClear
                      placeholder="使用默认模板"
                      options={deepAnalysisOptions}
                    />
                  </Form.Item>
                </Space>
              ),
            },
          ]}
          style={{ marginBottom: 16 }}
          defaultActiveKey={[]}
        />

        {/* 策略前提规则 */}
        <Collapse
          items={[
            {
              key: 'prerequisites',
              label: (
                <Space>
                  <SettingOutlined />
                  <span>策略前提规则（硬性约束）</span>
                  <Tag color="blue" style={{ marginLeft: 8 }}>
                    默认开启
                  </Tag>
                </Space>
              ),
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Card size="small">
                    <Form.Item
                      label="单仓规则"
                      name={['prerequisites', 'single_position', 'enabled']}
                      valuePropName="checked"
                      extra="同时只持有一个仓位，平仓后才可开新仓"
                    >
                      <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                    </Form.Item>
                  </Card>
                  <Card size="small">
                    <Form.Item
                      label="强制止损"
                      name={['prerequisites', 'mandatory_stop_loss', 'enabled']}
                      valuePropName="checked"
                      extra="每笔开仓必须设置止损价"
                    >
                      <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                    </Form.Item>
                    <Form.Item
                      label="默认止损百分比"
                      name={['prerequisites', 'mandatory_stop_loss', 'default_stop_loss_pct']}
                      tooltip="AI 未提供止损时的自动止损百分比"
                    >
                      <InputNumber
                        min={0.5}
                        max={20}
                        step={0.5}
                        addonAfter="%"
                        style={{ width: 160 }}
                      />
                    </Form.Item>
                  </Card>
                  <Card size="small">
                    <Form.Item
                      label="严格执规"
                      name={['prerequisites', 'strict_execution', 'enabled']}
                      valuePropName="checked"
                      extra="AI 决策必须严格遵循策略入场/出场规则，不可偏离"
                    >
                      <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                    </Form.Item>
                  </Card>
                </Space>
              ),
            },
          ]}
          style={{ marginBottom: 16 }}
          defaultActiveKey={[]}
        />

        <Alert
          message="配置锁定须知"
          description="回测开始后将锁定所有配置参数，不可修改。AI 调用可能消耗 Token，请合理设置回测范围。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          onClick={handleSubmit}
          loading={loading}
          disabled={disabled}
          block
        >
          {disabled ? '回测进行中...' : '开始回测'}
        </Button>
      </Form>
    </div>
  );
};
