import React from 'react';
import {
  Modal, Form, Select, Input, Space, Tag, Typography, Alert, message, Descriptions,
} from 'antd';
import { MergeCellsOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiBacktestApi, strategyApi } from '@/api';
import type { MergeOptimizeRequest } from '@/types/ai-backtest';

const { Text } = Typography;

interface Props {
  open: boolean;
  onClose: () => void;
  /** 预设的父回测 ID(可选) */
  defaultBacktestId?: string;
}

/**
 * 多策略融合优化弹窗
 *
 * 后端接口:
 *   POST /strategies/ai-backtest/{backtest_id}/merge-optimize
 *   请求体: { strategy_ids[], symbol, timeframe, name?, description? }
 *
 * 业务流程:
 *   1. 选择一个已完成的回测作为父回测(路径参数 backtest_id)
 *   2. 选择 2-5 个策略(注意:是策略ID,不是回测ID)
 *   3. 选择 symbol 和 timeframe
 *   4. 可选填写新策略名称
 */
const MergeOptimizeModal: React.FC<Props> = ({ open, onClose, defaultBacktestId }) => {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  // 获取已完成回测列表(用于选择父回测)
  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['ai-backtest', 'history', 'completed'],
    queryFn: () => aiBacktestApi.getHistory(1, 50),
    enabled: open,
  });

  const completedBacktests = (historyData?.data?.items || []).filter(
    (item: any) => item.status === 'completed',
  );

  // 获取策略列表(用于选择参与融合的策略)
  const { data: strategiesData, isLoading: strategiesLoading } = useQuery({
    queryKey: ['strategies', 'list', 'for-merge'],
    queryFn: () => strategyApi.list(),
    enabled: open,
  });

  const strategies = (strategiesData?.data as any) || [];

  const mergeMutation = useMutation({
    mutationFn: ({ backtestId, payload }: { backtestId: string; payload: Omit<MergeOptimizeRequest, 'backtest_id'> }) =>
      aiBacktestApi.mergeOptimize(backtestId, payload),
    onSuccess: (res) => {
      const result = (res as any)?.data ?? res;
      message.success(
        `融合优化完成: 已生成新策略「${result?.strategy_name ?? '未命名'}」并启动子回测`,
      );
      queryClient.invalidateQueries({ queryKey: ['ai-backtest'] });
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      form.resetFields();
      onClose();
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail;
      let errMsg = '融合优化失败';
      if (Array.isArray(detail)) {
        errMsg = detail.map((d: any) => `${(d.loc || []).join('.')}: ${d.msg}`).join('; ');
      } else if (typeof detail === 'string') {
        errMsg = detail;
      } else if (err?.message) {
        errMsg = err.message;
      }
      message.error(errMsg);
    },
  });

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      const backtestId = values.parentBacktestId || defaultBacktestId;
      if (!backtestId) {
        message.error('请选择父回测');
        return;
      }
      mergeMutation.mutate({
        backtestId,
        payload: {
          strategy_ids: values.strategyIds,
          symbol: values.symbol,
          timeframe: values.timeframe,
          name: values.name || undefined,
          description: values.description || undefined,
        },
      });
    } catch {
      // 校验失败，antd 会自动展示提示
    }
  };

  const handleCancel = () => {
    if (mergeMutation.isPending) return;
    form.resetFields();
    onClose();
  };

  // 回测选项(显示 strategy_name + symbol + 盈亏)
  const backtestOptions = completedBacktests.map((bt: any) => ({
    value: bt.id,
    label: `${bt.strategy_name} | ${bt.symbol} | ${bt.total_klines}根 | 盈亏${
      bt.total_pnl?.toFixed(0) ?? '?'
    }U`,
  }));

  // 策略选项(仅显示非草稿状态)
  const strategyOptions = (Array.isArray(strategies) ? strategies : [])
    .filter((s: any) => s.status !== 'draft')
    .map((s: any) => ({
      value: s.id,
      label: `${s.name}${s.description ? ` - ${s.description}` : ''}`,
    }));

  return (
    <Modal
      title={
        <Space>
          <MergeCellsOutlined />
          <span>多策略融合优化</span>
        </Space>
      }
      open={open}
      onCancel={handleCancel}
      onOk={handleOk}
      okText="开始融合"
      confirmLoading={mergeMutation.isPending}
      okButtonProps={{ disabled: mergeMutation.isPending }}
      cancelButtonProps={{ disabled: mergeMutation.isPending }}
      maskClosable={!mergeMutation.isPending}
      width={680}
      destroyOnHidden
    >
      {mergeMutation.isPending ? (
        <Alert
          type="info"
          showIcon
          message="AI 正在融合分析中..."
          description="请勿关闭窗口，AI 正在分析所选策略并生成融合后的新策略，同时会自动启动子回测。"
        />
      ) : (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message="多策略融合优化说明"
            description={
              <ul style={{ marginBottom: 0, paddingLeft: 18 }}>
                <li>
                  选择一个已完成的回测作为<b>父回测</b>(路径参数)
                </li>
                <li>
                  选择 2-5 个<b>策略</b>参与融合(策略ID,非回测ID)
                </li>
                <li>AI 将综合分析各策略规则与表现,取长补短</li>
                <li>生成一个全新的融合策略,并自动启动子回测</li>
                <li>原策略不会被修改</li>
              </ul>
            }
          />

          <Form
            form={form}
            layout="vertical"
            preserve={false}
            initialValues={{
              symbol: 'BTC/USDT',
              timeframe: '15m',
              parentBacktestId: defaultBacktestId,
            }}
          >
            <Form.Item
              name="parentBacktestId"
              label="父回测"
              tooltip="选择一个已完成的回测作为融合优化的父回测,新生成的子回测会关联此父回测"
              rules={[{ required: true, message: '请选择父回测' }]}
            >
              <Select
                placeholder="选择一个已完成的回测作为父回测"
                options={backtestOptions}
                loading={historyLoading}
                optionFilterProp="label"
                showSearch
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item
              name="strategyIds"
              label="参与融合的策略"
              rules={[
                { required: true, message: '请至少选择 2 个策略' },
                {
                  validator: (_, value: string[]) => {
                    if (!value || value.length === 0) return Promise.resolve();
                    if (value.length < 2) {
                      return Promise.reject(new Error('至少需要选择 2 个策略'));
                    }
                    if (value.length > 5) {
                      return Promise.reject(new Error('最多只能选择 5 个策略'));
                    }
                    return Promise.resolve();
                  },
                },
              ]}
              extra={<Text type="secondary">可选 2-5 个策略,注意是策略ID而非回测ID</Text>}
            >
              <Select
                mode="multiple"
                maxCount={5}
                placeholder="选择 2-5 个策略参与融合"
                options={strategyOptions}
                loading={strategiesLoading}
                optionFilterProp="label"
                showSearch
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Space style={{ width: '100%' }} size="middle">
              <Form.Item
                name="symbol"
                label="交易对"
                rules={[{ required: true, message: '请输入交易对' }]}
                style={{ flex: 1, marginBottom: 12 }}
              >
                <Input placeholder="BTC/USDT" maxLength={20} />
              </Form.Item>

              <Form.Item
                name="timeframe"
                label="时间周期"
                rules={[{ required: true, message: '请选择时间周期' }]}
                style={{ width: 160, marginBottom: 12 }}
              >
                <Select
                  options={[
                    { value: '15m', label: '15 分钟' },
                    { value: '1h', label: '1 小时' },
                    { value: '4h', label: '4 小时' },
                    { value: '1d', label: '1 天' },
                  ]}
                />
              </Form.Item>
            </Space>

            <Form.Item name="name" label="新策略名称" tooltip="可选,留空则由 AI 自动生成">
              <Input placeholder="可选,留空由 AI 自动命名" maxLength={200} showCount />
            </Form.Item>

            <Form.Item name="description" label="新策略描述" tooltip="可选">
              <Input.TextArea
                placeholder="可选,对新策略的描述说明"
                rows={2}
                maxLength={500}
                showCount
              />
            </Form.Item>
          </Form>

          {completedBacktests.length > 0 && (
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="可用父回测">
                <Tag color="success">{completedBacktests.length} 个已完成</Tag>
              </Descriptions.Item>
            </Descriptions>
          )}
        </Space>
      )}
    </Modal>
  );
};

// 同时支持命名导入（AIBacktestPanel 使用）和默认导入
export { MergeOptimizeModal };
export default MergeOptimizeModal;
