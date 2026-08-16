# AI 回测 K 线分析优化 - 前端技术方案

## 1. 概述

基于架构设计文档，实现前端与 AI 回测优化相关的功能变更，包括多策略选择、本地模型辅助配置、融合优化入口、进度展示优化。

---

## 2. 文件变更清单

| 文件                                                                | 操作 | 说明                                               |
| ------------------------------------------------------------------- | ---- | -------------------------------------------------- |
| `frontend/src/types/ai-backtest.ts`                                 | 修改 | 新增字段和类型定义                                 |
| `frontend/src/api/ai-backtest.ts`                                   | 修改 | 新增多策略融合 API                                 |
| `frontend/src/pages/strategies/components/AIBacktestConfigForm.tsx` | 修改 | 新增多策略选择器 + 本地模型辅助开关 + K 线数量配置 |
| `frontend/src/pages/strategies/components/AIBacktestPanel.tsx`      | 修改 | 新增融合优化逻辑                                   |
| `frontend/src/pages/strategies/components/AIBacktestProgress.tsx`   | 修改 | 优化进度展示（含本地模型预筛信息）                 |
| `frontend/src/pages/strategies/components/AIBacktestResult.tsx`     | 修改 | 新增效能统计和融合入口                             |
| `frontend/src/pages/strategies/components/MergeOptimizeModal.tsx`   | 新增 | 融合优化弹窗组件                                   |

---

## 3. 类型定义变更

### 3.1 AIBacktestConfig 扩展

```typescript
// frontend/src/types/ai-backtest.ts

// 新增：回测效能统计
export interface AIBacktestEfficiency {
  ai_call_count: number; // AI 调用次数
  precheck_total: number; // 快速预筛总次数
  precheck_triggered: number; // 触发 AI 分析次数
  precheck_efficiency: number; // 预筛效率（triggered/total）
  estimated_saved_calls: number; // 预估节省的 AI 调用次数
}

// AIBacktestConfig 扩展多策略和本地模型字段
export interface AIBacktestConfig {
  // ... 现有字段 ...
  strategyIds?: string[]; // 新增：多个策略 ID（多策略同时回测）
  useLocalModel?: boolean; // 新增：使用本地模型预筛
  localModelKlines?: number; // 新增：本地模型分析的 K 线数量
}

// AIBacktestCreateRequest 扩展
export interface AIBacktestCreateRequest {
  // ... 现有字段 ...
  strategy_ids?: string[]; // 新增：多个策略 ID
  use_local_model?: boolean; // 新增：使用本地模型预筛
  local_model_klines?: number; // 新增：本地模型分析的 K 线数量
}

// AIBacktestProgress 扩展
export interface AIBacktestProgress {
  // ... 现有字段 ...
  precheck_total?: number; // 新增：快速预筛总次数
  precheck_triggered?: number; // 新增：触发 AI 分析次数
  precheck_mode?: string; // 新增：预筛模式（rule_engine / local_model）
  has_position?: boolean; // 新增：是否有持仓
  ai_analysis_paused?: boolean; // 新增：AI 分析是否暂停
  analysis_window?: {
    // 新增：AI 分析窗口信息
    start: number;
    end: number;
    size: number;
  };
  trigger_reason?: string; // 新增：触发 AI 分析的原因
}

// AIBacktestDetail 扩展
export interface AIBacktestDetail {
  // ... 现有字段 ...
  ai_call_count?: number; // AI 调用总次数
  precheck_total?: number; // 快速预筛总次数
  precheck_triggered?: number; // 预筛触发 AI 分析次数
  use_local_model?: boolean; // 是否使用本地模型预筛
  local_model_klines?: number; // 本地模型分析的 K 线数量
  parent_backtest_id?: string; // 父回测 ID
  strategy_ids?: string[]; // 策略 ID 列表
}

// 新增：融合优化请求
export interface MergeOptimizeRequest {
  backtest_ids: string[];
  new_strategy_name?: string;
}

// 新增：融合优化结果
export interface MergeOptimizeResult {
  id: string;
  name: string;
  rules: Record<string, any>;
  source_backtest_ids: string[];
  source_strategy_names: string[];
}

// 新增：多策略回测创建结果
export interface MultiBacktestCreateResult {
  backtests: Array<{
    id: string;
    strategy_id: string;
    strategy_name: string;
    status: string;
  }>;
}
```

---

## 4. API 变更

### 4.1 新增 API 方法

```typescript
// frontend/src/api/ai-backtest.ts

export const aiBacktestApi = {
  // ... 现有方法 ...

  /** 多策略融合优化 */
  mergeOptimize: (data: MergeOptimizeRequest) =>
    request.post<MergeOptimizeResult>(
      "/strategies/ai-backtest/merge-optimize",
      data,
    ),

  /** 创建多策略回测 */
  createMulti: (data: AIBacktestCreateRequest & { strategy_ids: string[] }) =>
    request.post<MultiBacktestCreateResult>(
      "/strategies/ai-backtest/multi",
      data,
    ),
};
```

### 4.2 创建回测接口变更

当 `strategy_ids` 有值时，调用 `createMulti` 方法；否则调用原有的 `create` 方法：

```typescript
// 创建回测时的逻辑分支
const handleStart = () => {
  if (config.strategyIds && config.strategyIds.length > 0) {
    // 多策略回测
    createMultiMutation.mutate({
      ...payload,
      strategy_ids: config.strategyIds,
    });
  } else {
    // 单策略回测
    createMutation.mutate(payload);
  }
};
```

---

## 5. 组件变更

### 5.1 AIBacktestConfigForm - 多策略选择器 + 本地模型辅助配置

#### 多策略选择器

在现有表单中新增多策略选择区域（与之前一致）：

```tsx
// frontend/src/pages/strategies/components/AIBacktestConfigForm.tsx

// 新增：多策略选择模式切换开关
<Form.Item label="回测模式" name="backtestMode">
  <Radio.Group
    options={[
      { label: '单策略回测', value: 'single' },
      { label: '多策略回测', value: 'multi' },
    ]}
  />
</Form.Item>

// 条件渲染：多策略选择器（当 backtestMode === 'multi' 时显示）
{config.backtestMode === 'multi' && (
  <Card ...>
    <Form.Item name="strategyIds" ...>
      <Select mode="multiple" ... />
    </Form.Item>
  </Card>
)}
```

#### 本地模型辅助配置

在现有表单中新增本地模型辅助开关，与主 AI 粗略预筛互斥：

```tsx
// 新增：预筛模式配置
<Card
  size="small"
  title={
    <Space>
      <RobotOutlined />
      <span>AI 预筛配置</span>
      <Tag color="purple">可选增强</Tag>
    </Space>
  }
  style={{ marginBottom: 16 }}>
  <Form.Item
    name="useLocalModel"
    label="本地模型辅助"
    valuePropName="checked"
    extra={
      <Text type="secondary">
        开启后使用本地 Ollama 模型替代主 AI 进行预筛，零成本但分析能力较弱
      </Text>
    }>
    <Switch
      checkedChildren="本地模型"
      unCheckedChildren="主AI预筛"
      checked={config.useLocalModel}
      onChange={(checked) => {
        form.setFieldValue("useLocalModel", checked);
      }}
    />
  </Form.Item>

  {/* 条件渲染：预筛 K 线数量（两种模式共享） */}
  <Form.Item
    name="localModelKlines"
    label="预筛 K 线数量"
    tooltip="第一级粗略预筛分析的最新 K 线数量，越多越准确但越慢"
    rules={[{ required: true, message: "请设置预筛 K 线数量" }]}
    initialValue={10}>
    <InputNumber
      min={5}
      max={50}
      step={5}
      style={{ width: 200 }}
      addonAfter="根"
      placeholder="建议 10-20 根"
    />
  </Form.Item>

  {/* 预筛模式说明 */}
  <Alert
    type="info"
    showIcon
    message={
      <Space>
        <Text strong>当前预筛模式: </Text>
        <Tag color={config.useLocalModel ? "purple" : "blue"}>
          {config.useLocalModel ? "本地模型" : "主AI粗略预筛"}
        </Tag>
        <Text type="secondary">
          {config.useLocalModel
            ? `本地模型分析最近 ${config.localModelKlines || 10} 根 K 线，满足条件后触发主 AI 深度分析`
            : `主AI分析最近 ${config.localModelKlines || 10} 根 K 线，粗略判断是否满足策略入场条件，满足后触发深度分析`}
        </Text>
      </Space>
    }
    style={{ marginTop: 8 }}
  />
</Card>
```

```tsx
// frontend/src/pages/strategies/components/AIBacktestConfigForm.tsx

// 新增：多策略选择模式切换开关
<Form.Item label="回测模式" name="backtestMode">
  <Radio.Group
    options={[
      { label: "单策略回测", value: "single" },
      { label: "多策略回测", value: "multi" },
    ]}
  />
</Form.Item>;

// 条件渲染：多策略选择器（当 backtestMode === 'multi' 时显示）
{
  config.backtestMode === "multi" && (
    <Card
      size="small"
      title={
        <Space>
          <AppstoreAddOutlined />
          <span>选择多个策略进行 AI 回测</span>
          <Tag color="blue">融合优化</Tag>
        </Space>
      }
      style={{ marginBottom: 16, borderColor: "#1677ff" }}
      extra={
        <Text type="secondary">选择 2-5 个策略，回测完成后可进行融合优化</Text>
      }>
      <Form.Item
        name="strategyIds"
        label="参与策略"
        rules={[
          { required: true, message: "请选择至少 2 个策略" },
          {
            type: "array",
            min: 2,
            max: 5,
            message: "请选择 2-5 个策略",
          },
        ]}>
        <Select
          mode="multiple"
          placeholder="选择 2-5 个策略（回测后 AI 融合生成新策略）"
          showSearch
          optionFilterProp="label"
          maxCount={5}
          options={(strategies || []).map((s) => ({
            label: s.name,
            value: s.id,
          }))}
        />
      </Form.Item>
    </Card>
  );
}
```

### 5.2 AIBacktestPanel - 融合优化逻辑

```tsx
// frontend/src/pages/strategies/components/AIBacktestPanel.tsx

// 新增状态
const [mergeModalOpen, setMergeModalOpen] = useState(false);
const [completedBacktestIds, setCompletedBacktestIds] = useState<string[]>([]);

// 多策略回测 mutation
const createMultiMutation = useMutation({
  mutationFn: (data: Parameters<typeof aiBacktestApi.createMulti>[0]) =>
    aiBacktestApi.createMulti(data),
  onSuccess: (res) => {
    const btIds = res.data.backtests.map((b) => b.id);
    setCurrentBacktestId(btIds[0]); // 跟踪第一个
    setCompletedBacktestIds([]);
    setIsRunning(true);
    setActiveTab("progress");
  },
  onError: (err: any) => {
    message.error("创建多策略回测失败: " + (err?.message || "未知错误"));
  },
});

// 融合优化 mutation
const mergeOptimizeMutation = useMutation({
  mutationFn: (data: MergeOptimizeRequest) => aiBacktestApi.mergeOptimize(data),
  onSuccess: (res) => {
    message.success("融合策略已生成: " + res.data.name);
    queryClient.invalidateQueries({ queryKey: ["strategies", "list"] });
    setMergeModalOpen(false);
  },
  onError: (err: any) => {
    message.error("融合优化失败: " + (err?.message || "未知错误"));
  },
});

// 处理多策略 SSE 完成事件
const handleMultiSSEDone = useCallback(() => {
  setIsRunning(false);
  queryClient.invalidateQueries({ queryKey: ["ai-backtest", "history"] });

  // 收集已完成的回测 ID
  // 多策略回测时，每个策略独立回测，需要等待所有回测完成
  // 当前简化方案：用户手动选择已完成回测进行融合
}, [queryClient]);

// 在 handleStart 中增加分支
const handleStart = () => {
  if (config.strategyIds && config.strategyIds.length > 0) {
    createMultiMutation.mutate({
      ...payload,
      strategy_ids: config.strategyIds,
    });
  } else {
    createMutation.mutate(payload);
  }
};

// 在历史 Tab 中新增"融合优化"按钮
// 当用户选择多个已完成回测后，可点击融合
```

### 5.3 AIBacktestProgress - 优化展示

```tsx
// frontend/src/pages/strategies/components/AIBacktestProgress.tsx

// 新增：快速预筛统计展示
{
  progress.precheck_total !== undefined && (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space wrap>
        <Text strong>过滤效能: </Text>
        <Tag color="blue">预筛 {progress.precheck_total} 次</Tag>
        <Tag color="green">触发 AI {progress.precheck_triggered} 次</Tag>
        {progress.precheck_total > 0 && (
          <Tag color="purple">
            触发率{" "}
            {(
              ((progress.precheck_triggered || 0) / progress.precheck_total) *
              100
            ).toFixed(1)}
            %
          </Tag>
        )}
        <Tag
          color={progress.precheck_mode === "local_model" ? "purple" : "blue"}>
          {progress.precheck_mode === "local_model"
            ? "本地模型预筛"
            : "主AI粗略预筛"}
        </Tag>
        <Text type="secondary">
          AI 调用 {progress.precheck_triggered || 0} 次 (预估节省{" "}
          {progress.precheck_total - (progress.precheck_triggered || 0)} 次)
        </Text>
      </Space>
    </Card>
  );
}

// 新增：持仓状态指示器
{
  progress.current_position?.has_position && (
    <Alert
      type="info"
      showIcon
      icon={<StopOutlined />}
      message={
        <Space>
          <Text strong>AI 分析已暂停</Text>
          <Tag
            color={
              progress.current_position.direction === "long" ? "red" : "green"
            }>
            {progress.current_position.direction === "long" ? "多头" : "空头"}
            持仓中
          </Tag>
          <Text type="secondary">持仓期间暂停 AI 分析，平仓后自动恢复</Text>
        </Space>
      }
      style={{ marginBottom: 16 }}
    />
  );
}

// 新增：AI 分析触发原因展示
{
  progress.trigger_reason && (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space>
        <Text strong>触发 AI 分析: </Text>
        <Tag color="orange">{progress.trigger_reason}</Tag>
      </Space>
    </Card>
  );
}

// 新增：AI 分析窗口信息
{
  progress.analysis_window && (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space wrap>
        <Text strong>AI 分析窗口: </Text>
        <Text>
          K 线 {progress.analysis_window.start} - {progress.analysis_window.end}
        </Text>
        <Text type="secondary">共 {progress.analysis_window.size} 根</Text>
      </Space>
    </Card>
  );
}
```

### 5.4 AIBacktestResult - 融合优化入口

```tsx
// frontend/src/pages/strategies/components/AIBacktestResult.tsx

// 新增：融合优化按钮区域
{
  detail?.status === "completed" && onMergeOptimize && (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Space>
        <Button
          icon={<MergeCellsOutlined />}
          type="primary"
          ghost
          onClick={() => onMergeOptimize?.()}>
          融合优化
        </Button>
        <Text type="secondary">
          选择多个已完成回测，AI 综合分析后生成融合策略
        </Text>
      </Space>
    </Card>
  );
}
```

### 5.5 MergeOptimizeModal - 新增组件

```tsx
// frontend/src/pages/strategies/components/MergeOptimizeModal.tsx

import React, { useState } from "react";
import {
  Modal,
  Form,
  Select,
  Input,
  Space,
  Tag,
  Typography,
  Alert,
  message,
} from "antd";
import { MergeCellsOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { aiBacktestApi } from "@/api/ai-backtest";

const { Text } = Typography;

interface Props {
  open: boolean;
  onClose: () => void;
}

export const MergeOptimizeModal: React.FC<Props> = ({ open, onClose }) => {
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  // 获取历史回测列表（已完成）
  const { data: historyData } = useQuery({
    queryKey: ["ai-backtest", "history", "completed"],
    queryFn: () => aiBacktestApi.getHistory(1, 50),
    enabled: open,
  });

  const completedBacktests = (historyData?.data?.items || []).filter(
    (item: any) => item.status === "completed",
  );

  const mergeMutation = useMutation({
    mutationFn: (data: any) => aiBacktestApi.mergeOptimize(data),
    onSuccess: (res) => {
      message.success("融合策略已生成: " + res.data.name);
      queryClient.invalidateQueries({ queryKey: ["strategies", "list"] });
      onClose();
      form.resetFields();
    },
    onError: (err: any) => {
      message.error("融合优化失败: " + (err?.message || "未知错误"));
    },
  });

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      mergeMutation.mutate({
        backtest_ids: values.backtestIds,
        new_strategy_name: values.name || undefined,
      });
    } catch {
      // 表单校验失败
    }
  };

  return (
    <Modal
      title={
        <Space>
          <MergeCellsOutlined />
          <span>多策略融合优化</span>
        </Space>
      }
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={mergeMutation.isPending}
      okText="开始融合"
      cancelText="取消"
      width={600}>
      <Alert
        message="融合优化说明"
        description={
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            <li>选择 2-5 个已完成的 AI 回测</li>
            <li>AI 会综合分析每个策略的规则和回测表现</li>
            <li>取长补短，生成一个全新的融合策略</li>
            <li>原策略不会被修改，融合策略是独立的新策略</li>
          </ul>
        }
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Form form={form} layout="vertical" initialValues={{ name: "" }}>
        <Form.Item
          name="backtestIds"
          label="选择回测"
          rules={[
            { required: true, message: "请选择至少 2 个回测" },
            {
              type: "array",
              min: 2,
              max: 5,
              message: "请选择 2-5 个已完成回测",
            },
          ]}>
          <Select
            mode="multiple"
            placeholder="选择 2-5 个已完成回测"
            maxCount={5}
            optionFilterProp="label"
            options={completedBacktests.map((bt: any) => ({
              label: `${bt.strategy_name} | ${bt.symbol} | ${bt.total_klines}根 | 盈亏${bt.total_pnl?.toFixed(0) || "?"}U`,
              value: bt.id,
            }))}
          />
        </Form.Item>

        <Form.Item name="name" label="新策略名称（可选）">
          <Input placeholder="留空则自动生成" maxLength={100} showCount />
        </Form.Item>
      </Form>

      {mergeMutation.isPending && (
        <Alert message="AI 正在融合分析中..." type="warning" showIcon />
      )}
    </Modal>
  );
};
```

---

## 6. 组件架构图

```
AIBacktestPanel
├── AIBacktestConfigForm
│   ├── 单策略配置表单（现有）
│   ├── 多策略选择器（新增）
│   └── 本地模型辅助配置（新增）
│       ├── useLocalModel 开关
│       └── localModelKlines 数量配置
├── AIBacktestProgressComp
│   ├── 进度条（现有）
│   ├── 技术指标（现有）
│   ├── AI 实时分析（现有）
│   ├── 快速预筛统计（新增）
│   ├── 预筛模式标签（新增）
│   ├── 持仓暂停指示器（新增）
│   └── AI 分析窗口信息（新增）
├── AIBacktestResult
│   ├── 基本信息（现有）
│   ├── 指标卡片（现有）
│   ├── 交易明细表（现有）
│   ├── AI 分析入口（现有）
│   └── 融合优化入口（新增）
├── AIBacktestAnalysis（现有）
├── AIBacktestHistory（现有）
└── MergeOptimizeModal（新增）
```

---

## 7. 交互流程

### 7.1 单策略回测流程（不变）

```
选择单个策略 → 配置参数（可选开启本地模型辅助） → 开始回测 → 查看进度 → 查看结果
→ AI 分析回测结果 → 策略优化（生成新策略）
```

### 7.2 多策略回测 + 融合优化流程（新增）

```
选择"多策略回测"模式 → 选择 2-5 个策略 → 配置参数
→ 开始多策略回测 → 分别查看每个策略的进度
→ 所有回测完成后 → 点击"融合优化"
→ 打开 MergeOptimizeModal → 选择需要融合的回测
→ 确认融合 → AI 生成融合策略 → 跳转到新策略详情
```

### 7.3 优化前后对比（进度页）

| 功能          | 优化前                | 优化后                                 |
| ------------- | --------------------- | -------------------------------------- |
| AI 调用次数   | 300 次（300 根 K 线） | 10-20 次                               |
| 回测耗时      | 25 分钟               | ~1 分钟                                |
| 持仓期间      | 继续调用 AI（浪费）   | 暂停 AI 分析                           |
| 预筛方式      | 无                    | 主AI粗略预筛 或 本地模型（可切换）     |
| 预筛 K 线数量 | 无                    | 可配置 5-50 根（默认 10 根）           |
| 进度信息      | 仅进度条              | 含预筛统计、预筛模式标签、持仓暂停状态 |

---

## 8. 状态管理

### 8.1 组件状态矩阵

| 状态       | 操作可用性                      | 说明           |
| ---------- | ------------------------------- | -------------- |
| 未开始回测 | 可配置、可开始                  | 默认状态       |
| 回测进行中 | 可停止、可查看进度              | 配置表单禁用   |
| 回测完成   | 可查看结果、AI 分析、优化、融合 | 进度页显示完成 |
| 回测失败   | 可查看错误信息                  | 不可分析/优化  |
| 回测取消   | 仅可查看历史                    | 不可分析/优化  |

### 8.2 多策略回测状态

多策略回测时，前端需要跟踪每个子回测的进度：

```typescript
interface MultiBacktestState {
  backtests: Array<{
    id: string;
    strategyId: string;
    strategyName: string;
    status: string;
    progress: number;
  }>;
  allCompleted: boolean;
}
```

---

## 9. 错误处理

| 错误场景           | 处理方式                     |
| ------------------ | ---------------------------- |
| 选择少于 2 个策略  | 表单校验提示                 |
| 选择多于 5 个策略  | Select 的 maxCount 限制      |
| 选中的回测尚未完成 | 后端校验后返回错误           |
| 融合优化超时       | 显示加载状态，超时后提示重试 |

---

## 10. 测试要点

| 测试项         | 说明                               |
| -------------- | ---------------------------------- |
| 多策略选择器   | 选择 2-5 个策略，确认表单校验正确  |
| 多策略回测启动 | 确认调用 createMulti API           |
| 融合优化弹窗   | 弹窗列表只显示已完成的回测         |
| 融合优化执行   | 确认调用 mergeOptimize API         |
| 进度展示优化   | 确认预筛统计、持仓暂停状态正确展示 |
| 多策略回测 SSE | 确认每个子回测的进度正确推送       |

---

## 11. 思维导图补充需求（前端实现）

### 11.1 类型定义扩展

```typescript
// frontend/src/types/ai-backtest.ts

// 关键位
export interface KeyLevel {
  type: 'support' | 'resistance';
  price: number;
  hit_price?: number;
  distance_pct?: number;
}

// 开单事件
export interface LatestTradeEvent {
  id: string;
  direction: 'long' | 'short';
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  quantity: number;
  created_at: string;
}

// 平仓事件
export interface ClosedTradeEvent {
  id: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  reason: 'stop_loss' | 'take_profit' | 'manual' | 'rule';
  closed_at: string;
}

// AI 深度分析摘要（SSE推送）
export interface AIAnalysisMini {
  trend: 'bullish' | 'bearish' | 'neutral';
  key_levels: KeyLevel[];
  decision: 'open_long' | 'open_short' | 'close_long' | 'close_short' | 'hold';
  confidence: number;
  reasoning: string;
}

// 深度分析日志（历史复盘用）
export interface AIAnalysisLogItem {
  kline_index: number;
  trigger: 'precheck_pass' | 'key_level_hit' | 'position_closed' | 'initial';
  trigger_reason: string;
  analysis: AIAnalysisMini;
  created_at: string;
}

// 初始化分析结果
export interface InitialAnalysis {
  trend: 'bullish' | 'bearish' | 'neutral';
  trend_summary: string;
  key_levels: KeyLevel[];
}

// Prompt 模板
export interface PromptTemplate {
  id: string;
  name: string;
  category: 'backtest_precheck' | 'deep_analysis' | 'merge_optimize' | 'initial_analysis';
  content: string;
  description?: string;
  variables?: Record<string, string>;
  is_default: boolean;
  is_system: boolean;
  created_at: string;
}

// Progress payload 新增
export interface AIBacktestProgress {
  // ... 现有字段 ...
  precheck_total?: number;
  precheck_triggered?: number;
  precheck_mode?: string;
  has_position?: boolean;
  ai_analysis_paused?: boolean;
  analysis_window?: { start: number; end: number; size: number };
  trigger_reason?: string;

  // 思维导图新增
  kline_window?: Array<{ open: number; high: number; low: number; close: number; volume: number; time: string }>;
  current_kline_index?: number;
  latest_trade?: LatestTradeEvent;          // 开单事件（单次）
  closed_trade?: ClosedTradeEvent;          // 平仓事件（单次）
  ai_analysis?: AIAnalysisMini;             // AI 分析摘要
  key_levels?: KeyLevel[];                  // 最新关键位
  trend?: 'bullish' | 'bearish' | 'neutral';
}

// AIBacktestDetail 扩展
export interface AIBacktestDetail {
  // ... 现有字段 ...
  initial_analysis?: InitialAnalysis;
  ai_analysis_logs?: AIAnalysisLogItem[];
  prompt_template_ids?: Record<string, string | null>;
}

// AIBacktestConfig 扩展
export interface AIBacktestConfig {
  // ... 现有字段 ...
  promptTemplateIds?: Record<string, string | null>;
}
```

### 11.2 API 扩展

```typescript
// frontend/src/api/ai-backtest.ts
export const aiBacktestApi = {
  // ... 现有 ...
};

// 新增：Prompt 模板 API
import { request } from '@/utils/request';
import type { PromptTemplate } from '@/types/ai-backtest';

export const promptTemplateApi = {
  list: (category?: string) =>
    request.get<PromptTemplate[]>('/prompt-templates', { params: { category } }),

  create: (data: Pick<PromptTemplate, 'name' | 'category' | 'content' | 'description' | 'variables'>) =>
    request.post<PromptTemplate>('/prompt-templates', data),

  update: (id: string, data: Partial<Pick<PromptTemplate, 'name' | 'content' | 'description' | 'variables'>>) =>
    request.put<PromptTemplate>(`/prompt-templates/${id}`, data),

  remove: (id: string) =>
    request.delete<boolean>(`/prompt-templates/${id}`),
};

// 系统配置 API：确保 AI 配置表单中移除 api_key
// GET /system/configs/ai 返回时已剔除 api_key；POST/PUT 时也自动忽略
```

### 11.3 回测进度动画（K 线滚动 + 开单标记）

#### 组件：AIBacktestKlineChart（新增）

```tsx
// frontend/src/pages/strategies/components/AIBacktestKlineChart.tsx
/**
 * 回测进度动画图表
 * - 接收 SSE 的 kline_window：最多 300 根，滚动渲染
 * - 关键位：画线标记支撑/压力
 * - 开单事件：在开仓价处画多/空图标
 * - 平仓事件：画虚线并显示盈亏
 */
import React, { useEffect, useRef, useMemo } from 'react';
import { useTheme } from 'antd';

interface Props {
  klineWindow: any[];                       // SSE 推送的滚动 K 线
  keyLevels: KeyLevel[];                    // 关键位
  trades: Array<{ event: 'open' | 'close'; data: any }>;  // 已发生的开/平仓事件列表
  currentIndex?: number;                    // 当前推进到第几根
  height?: number;
}

export const AIBacktestKlineChart: React.FC<Props> = ({
  klineWindow, keyLevels, trades, currentIndex, height = 360,
}) => {
  // 使用 lightweight-charts（或 ECharts K 线）
  // 初始化时渲染预热K线，后续 append 追加
  // 关键位 → priceLine
  // 开仓 → marker shape 为 arrowUp/arrowDown
  // 平仓 → marker + pnl 标签
  // 每次推进到 currentIndex 时，确保最后一根 K 线高亮显示
  return (
    <div className="ai-backtest-kline-chart">
      {/* lightweight-charts / ECharts 渲染 */}
    </div>
  );
};
```

#### 在 AIBacktestProgress 中集成

```tsx
{/* 进度动画 K 线图 */}
<Card size="small" title="回测进度动画" style={{ marginBottom: 16 }}>
  <AIBacktestKlineChart
    klineWindow={progress.kline_window || []}
    keyLevels={progress.key_levels || []}
    trades={accumulatedTrades}  // 从 SSE latest_trade / closed_trade 累积
    currentIndex={progress.current_kline_index}
  />
</Card>
```

#### SSE 事件累积（AIBacktestProgress 内部）

```typescript
const [accumulatedTrades, setAccumulatedTrades] = useState<
  Array<{ event: 'open' | 'close'; data: any; klineIndex: number }>
>([]);

useEffect(() => {
  if (sseProgress?.latest_trade && !seenTradeIds.has(sseProgress.latest_trade.id)) {
    seenTradeIds.add(sseProgress.latest_trade.id);
    setAccumulatedTrades(prev => [
      ...prev,
      { event: 'open', data: sseProgress.latest_trade, klineIndex: sseProgress.current_kline_index },
    ]);
  }
  if (sseProgress?.closed_trade && !seenTradeIds.has(sseProgress.closed_trade.id + '-close')) {
    seenTradeIds.add(sseProgress.closed_trade.id + '-close');
    setAccumulatedTrades(prev => [
      ...prev,
      { event: 'close', data: sseProgress.closed_trade, klineIndex: sseProgress.current_kline_index },
    ]);
  }
}, [sseProgress]);
```

### 11.4 AI 分析数据实时展示

#### 组件：AIAnalysisRealtimePanel（新增或增强现有）

```tsx
// 展示趋势 + 关键位 + 最新 AI 分析 + 当前持仓

<Card size="small" title="AI 实时分析" style={{ marginBottom: 16 }}>
  <Space direction="vertical" style={{ width: '100%' }}>
    {/* 整体趋势标签 */}
    <Row gutter={8} align="middle">
      <Col>
        <Tag color={
          progress.trend === 'bullish' ? 'red' :
          progress.trend === 'bearish' ? 'green' : 'default'
        }>
          {progress.trend === 'bullish' ? '看涨' : progress.trend === 'bearish' ? '看跌' : '震荡'}
        </Tag>
      </Col>
      <Col>
        <Text type="secondary">{progress.ai_analysis?.trend_summary || initialAnalysis?.trend_summary}</Text>
      </Col>
    </Row>

    {/* 关键位列表 */}
    <div>
      <Text strong>关键位: </Text>
      <Space wrap>
        {(progress.key_levels || []).map((lvl, i) => (
          <Tag key={i} color={lvl.type === 'support' ? 'cyan' : 'magenta'}>
            {lvl.type === 'support' ? '支撑' : '压力'} {lvl.price}
          </Tag>
        ))}
      </Space>
    </div>

    {/* 最新 AI 分析 */}
    {progress.ai_analysis && (
      <div style={{ padding: 8, background: token.colorBgContainer, borderRadius: 4 }}>
        <Row gutter={8}>
          <Col span={8}>
            <Text type="secondary">决策</Text>
            <div>
              <Tag color={
                progress.ai_analysis.decision === 'open_long' ? 'red' :
                progress.ai_analysis.decision === 'open_short' ? 'green' : 'default'
              }>
                {DECISION_LABEL[progress.ai_analysis.decision]}
              </Tag>
            </div>
          </Col>
          <Col span={8}>
            <Text type="secondary">置信度</Text>
            <div>
              <Rate disabled allowHalf value={progress.ai_analysis.confidence} count={5} />
            </div>
          </Col>
          <Col span={8}>
            <Text type="secondary">触发</Text>
            <div>
              <Tag>{progress.trigger_reason}</Tag>
            </div>
          </Col>
        </Row>
        <div style={{ marginTop: 8 }}>
          <Text type="secondary">分析理由:</Text>
          <Paragraph style={{ marginTop: 4 }} ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}>
            {progress.ai_analysis.reasoning}
          </Paragraph>
        </div>
      </div>
    )}

    {/* 当前持仓信息 */}
    {progress.has_position && progress.current_position && (
      <Card size="small" type="inner" title="当前持仓">
        <Descriptions column={2} size="small">
          <Descriptions.Item label="方向">
            <Tag color={progress.current_position.direction === 'long' ? 'red' : 'green'}>
              {progress.current_position.direction === 'long' ? '多单' : '空单'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="开仓价">{progress.current_position.entry_price}</Descriptions.Item>
          <Descriptions.Item label="止损" type="danger">{progress.current_position.stop_loss}</Descriptions.Item>
          <Descriptions.Item label="止盈" type="success">{progress.current_position.take_profit}</Descriptions.Item>
          <Descriptions.Item label="浮动盈亏" span={2}>
            <Text type={progress.current_position.unrealized_pnl >= 0 ? 'success' : 'danger'}>
              {progress.current_position.unrealized_pnl?.toFixed(2)} USDT
              ({progress.current_position.unrealized_pnl_pct?.toFixed(2)}%)
            </Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>
    )}
  </Space>
</Card>
```

### 11.5 Prompt 模板管理页面

#### 路由

```
/routes 新增:
/system/prompts                     列表页
/system/prompts/new                 新建
/system/prompts/:id/edit            编辑
```

#### 组件：PromptTemplateManagementPage（新增）

```tsx
// 结构
// ├── Tabs（按分类切换：预筛模板 / 深度分析模板 / 融合模板 / 初始化模板）
// ├── 列表 Table（名称、描述、类型、默认、操作）
// │   ├── 系统模板：不可删除，仅查看/复制为自定义
// │   └── 自定义模板：编辑/删除/设为默认
// └── Drawer（编辑或新建模板）
//       ├── 名称、分类、描述
//       ├── 内容（TextArea + 代码风格编辑）
//       └── 支持的变量提示（{变量名} 高亮）

// Tab 与分类映射
const CATEGORY_OPTIONS = [
  { value: 'initial_analysis', label: '初始化分析模板' },
  { value: 'backtest_precheck', label: '回测预筛模板' },
  { value: 'deep_analysis', label: '深度分析模板' },
  { value: 'merge_optimize', label: '多策略融合模板' },
];
```

### 11.6 回测配置表单：可选 Prompt 模板

在 `AIBacktestConfigForm` 中新增折叠面板：

```tsx
<Collapse
  items={[
    {
      key: 'prompt_templates',
      label: (
        <Space>
          <FileTextOutlined />
          <span>AI Prompt 模板（可选）</span>
          <Tag style={{ marginLeft: 8 }}>高级</Tag>
        </Space>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Form.Item name={['promptTemplateIds', 'initial_analysis']} label="初始化分析模板">
            <Select options={tplOpts('initial_analysis')} allowClear placeholder="使用系统默认" />
          </Form.Item>
          <Form.Item name={['promptTemplateIds', 'backtest_precheck']} label="预筛分析模板">
            <Select options={tplOpts('backtest_precheck')} allowClear placeholder="使用系统默认" />
          </Form.Item>
          <Form.Item name={['promptTemplateIds', 'deep_analysis']} label="深度分析模板">
            <Select options={tplOpts('deep_analysis')} allowClear placeholder="使用系统默认" />
          </Form.Item>
        </Space>
      ),
    },
  ]}
  style={{ marginBottom: 16 }}
  defaultActiveKey={[]}
/>
```

提交时将 `prompt_template_ids` 拼入请求体：

```ts
const payload = {
  // ...
  prompt_template_ids: Object.fromEntries(
    Object.entries(config.promptTemplateIds || {}).filter(([_, v]) => !!v)
  ),
};
```

### 11.7 回测结果：AI 分析日志复盘（历史可查看）

#### 组件：AIAnalysisLogsViewer（AIBacktestResult 内部增强）

```tsx
// 从 detail.ai_analysis_logs 中读取
// 展示为 Timeline：时间/触发原因/决策/理由

<Timeline
  items={(detail?.ai_analysis_logs || []).map(log => ({
    color: log.trigger === 'key_level_hit' ? 'magenta'
         : log.trigger === 'position_closed' ? 'orange' : 'blue',
    children: (
      <Card size="small" title={
        <Space>
          <Tag>K线 {log.kline_index}</Tag>
          <Tag color={
            log.trigger === 'precheck_pass' ? 'blue' :
            log.trigger === 'key_level_hit' ? 'magenta' :
            log.trigger === 'position_closed' ? 'orange' : 'purple'
          }>
            {TRIGGER_LABEL[log.trigger]}
          </Tag>
          <Text type="secondary">{log.trigger_reason}</Text>
        </Space>
      }>
        <Row gutter={8}>
          <Col span={12}>
            决策:
            <Tag color={DECISION_COLORS[log.analysis.decision]}>
              {DECISION_LABEL[log.analysis.decision]}
            </Tag>
            置信度: <Rate disabled allowHalf value={log.analysis.confidence} count={5} />
          </Col>
          <Col span={12}>
            关键位:
            {(log.analysis.key_levels || []).map((l, i) => (
              <Tag key={i} color={l.type === 'support' ? 'cyan' : 'magenta'}>
                {l.type === 'support' ? '支撑' : '压力'} {l.price}
              </Tag>
            ))}
          </Col>
        </Row>
        <Paragraph style={{ marginTop: 8 }}>
          {log.analysis.reasoning}
        </Paragraph>
      </Card>
    ),
  }))}
/>
```

### 11.8 AI 配置前端：隐藏 API Key 输入

在 `ProviderFormModal` 中移除 `api_key` 字段：

```tsx
// frontend/src/pages/system/ProviderFormModal.tsx

// 删除 Form.Item(api_key)
// 提交时 payload 中不包含 api_key
// 说明文字补充：
<Alert
  type="info"
  showIcon
  message="API Key 已改为环境变量配置"
  description="API Key 不再在前端输入或保存，需要在 backend/.env 中通过 LLM_OPENAI_API_KEY / LLM_DEEPSEEK_API_KEY / LLM_ZHIPU_API_KEY 等变量配置后重启服务生效。"
  style={{ marginBottom: 16 }}
/>
```

### 11.9 严格同步的前端感知（UX）

SSE 进度推送应包含 `current_kline_index`，前端显示进度条。如 K 线推进长时间停滞（如超过 N 秒），说明 AI 还在响应，前端显示：

```
<Alert
  type="info"
  showIcon
  message="AI 深度分析中..."
  description="当前 K 线正在等待 AI 返回结果，分析完成前不会推进下一根。"
/>
```

---

## 12. 更新后的测试要点（前端）

| 测试项 | 说明 |
|--------|------|
| K 线滚动动画 | 新 K 线 append 时，图表正确滚动保持 300 根显示 |
| 关键位画线 | 支撑位青色线、压力位品红色线，数量和价格正确 |
| 开单标记 | long/short 箭头出现在对应开仓 K 线上 |
| 平仓标记 | 平仓线与盈亏标签显示 |
| AI 分析实时展示 | 趋势、关键位、决策、理由、触发原因正确更新 |
| Prompt 模板 CRUD | 新建/编辑/删除自定义模板；系统模板不可删除 |
| 回测配置模板选择 | 四类模板可分别选择，提交时透传后端 |
| 历史分析日志 | Timeline 展示完整且可展开 |
| Provider 表单隐藏 API Key | 表单中无 api_key 输入，提交时不包含该字段 |
