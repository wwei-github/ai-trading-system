import React from 'react';
import {
  Modal, Form, Select, Input, Space, Tag, Typography, Alert, message,
} from 'antd';
import { MergeCellsOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { aiBacktestApi } from '@/api/ai-backtest';

const { Text } = Typography;

interface Props {
  open: boolean;
  onClose: () => void;
}

export const MergeOptimizeModal: React.FC<Props> = ({ open, onClose }) => {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['ai-backtest', 'history', 'completed'],
    queryFn: () => aiBacktestApi.getHistory(1, 50),
    enabled: open,
  });

  const completedBacktests = (historyData?.data?.items || []).filter(
    (item: any) => item.status === 'completed',
  );

  const mergeMutation = useMutation({
    mutationFn: (values: { backtest_ids: string[]; new_strategy_name?: string }) =>
      aiBacktestApi.mergeOptimize(values),
    onSuccess: (res) => {
      const result = (res as any)?.data ?? res;
      message.success(
        `融合优化完成：已生成新策略「${result?.name ?? '未命名'}」`,
      );
      queryClient.invalidateQueries({ queryKey: ['ai-backtest'] });
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      form.resetFields();
      onClose();
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || err?.message || '融合优化失败');
    },
  });

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      mergeMutation.mutate({
        backtest_ids: values.backtestIds,
        new_strategy_name: values.name,
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

  const selectOptions = completedBacktests.map((bt: any) => ({
    value: bt.id,
    label: `${bt.strategy_name} | ${bt.symbol} | ${bt.total_klines}根 | 盈亏${
      bt.total_pnl?.toFixed(0) || '?'
    }U`,
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
      width={640}
      destroyOnClose
    >
      {mergeMutation.isPending ? (
        <Alert
          type="info"
          showIcon
          message="AI 正在融合分析中..."
          description="请勿关闭窗口，AI 正在分析所选策略并生成融合后的新策略。"
        />
      ) : (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message="多策略融合优化说明"
            description={
              <ul style={{ marginBottom: 0, paddingLeft: 18 }}>
                <li>选择 2-5 个已完成的回测策略</li>
                <li>AI 将分析各策略的优势与不足</li>
                <li>生成一个融合各策略优点的新策略</li>
                <li>原策略不会被修改，仅生成新策略</li>
              </ul>
            }
          />

          <Form form={form} layout="vertical" preserve={false}>
            <Form.Item
              name="backtestIds"
              label="选择回测策略"
              rules={[
                { required: true, message: '请至少选择 2 个回测策略' },
                {
                  validator: (_, value: string[]) => {
                    if (!value || value.length === 0) return Promise.resolve();
                    if (value.length < 2) {
                      return Promise.reject(new Error('至少需要选择 2 个策略'));
                    }
                    return Promise.resolve();
                  },
                },
              ]}
              extra={<Text type="secondary">可选 2-5 个已完成的回测</Text>}
            >
              <Select
                mode="multiple"
                maxCount={5}
                placeholder="请选择 2-5 个已完成的回测"
                options={selectOptions}
                loading={historyLoading}
                optionFilterProp="label"
                showSearch
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item
              name="name"
              label="新策略名称"
              tooltip="可选，留空则由 AI 自动生成名称"
            >
              <Input
                placeholder="可选，留空由 AI 自动命名"
                maxLength={100}
                showCount
              />
            </Form.Item>
          </Form>

          {completedBacktests.length > 0 && (
            <Space size={[4, 4]} wrap>
              <Text type="secondary">已完成回测：</Text>
              <Tag color="success">{completedBacktests.length} 个可用</Tag>
            </Space>
          )}
        </Space>
      )}
    </Modal>
  );
};

export default MergeOptimizeModal;
