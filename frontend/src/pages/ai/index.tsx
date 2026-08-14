import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Row,
  Col,
  Card,
  List,
  Tag,
  Button,
  Input,
  Segmented,
  Space,
  Dropdown,
  Modal,
  Form,
  Select,
  Progress,
  Typography,
  message,
  Spin,
} from 'antd';
import type { MenuProps } from 'antd';
import {
  DeleteOutlined,
  SendOutlined,
  StopOutlined,
  RocketOutlined,
  FileTextOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  PageContainer,
  ConfirmButton,
  EmptyState,
} from '@/components/Common';
import { aiApi } from '@/api/ai';
import type {
  AiMode,
  AiConversation,
  AiMessage,
  TradingSignal,
  ReportPeriod,
  SignalRequest,
} from '@/types';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

const MODE_OPTIONS: Array<{ label: string; value: AiMode }> = [
  { label: '通用问答', value: 'general' },
  { label: '行情分析', value: 'market' },
  { label: '策略建议', value: 'strategy' },
  { label: '风险评估', value: 'risk' },
  { label: '学习辅导', value: 'tutor' },
];

const MODE_COLOR_MAP: Record<AiMode, string> = {
  general: 'blue',
  market: 'cyan',
  strategy: 'purple',
  risk: 'orange',
  tutor: 'green',
};

const MODE_LABEL_MAP: Record<AiMode, string> = {
  general: '通用问答',
  market: '行情分析',
  strategy: '策略建议',
  risk: '风险评估',
  tutor: '学习辅导',
};

const SYMBOL_OPTIONS = [
  { label: 'BTC/USDT', value: 'BTC/USDT' },
  { label: 'ETH/USDT', value: 'ETH/USDT' },
  { label: 'SOL/USDT', value: 'SOL/USDT' },
  { label: 'BNB/USDT', value: 'BNB/USDT' },
  { label: 'XRP/USDT', value: 'XRP/USDT' },
  { label: 'ADA/USDT', value: 'ADA/USDT' },
  { label: 'DOGE/USDT', value: 'DOGE/USDT' },
  { label: 'AVAX/USDT', value: 'AVAX/USDT' },
];

const STRATEGY_OPTIONS = [
  { label: '趋势跟踪', value: 'trend_following' },
  { label: '均值回归', value: 'mean_reversion' },
  { label: '突破交易', value: 'breakout' },
  { label: '网格交易', value: 'grid' },
  { label: 'MACD策略', value: 'macd' },
  { label: 'RSI策略', value: 'rsi' },
];

const TIMEFRAME_OPTIONS = [
  { label: '5分钟', value: '5m' },
  { label: '15分钟', value: '15m' },
  { label: '1小时', value: '1h' },
  { label: '4小时', value: '4h' },
  { label: '日线', value: '1d' },
  { label: '周线', value: '1w' },
];

const SIDE_COLOR_MAP: Record<string, string> = {
  buy: 'green',
  sell: 'red',
  hold: 'gold',
};

const SIDE_LABEL_MAP: Record<string, string> = {
  buy: '买入',
  sell: '卖出',
  hold: '持有',
};

const REPORT_PERIOD_OPTIONS: Array<{ key: ReportPeriod; label: string }> = [
  { key: 'daily', label: '日报' },
  { key: 'weekly', label: '周报' },
  { key: 'monthly', label: '月报' },
];

const renderMarkdownContent = (content: string) => {
  const lines = content.split('\n');
  const elements: JSX.Element[] = [];
  let listItems: string[] = [];
  let keyCounter = 0;

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${keyCounter++}`} style={{ paddingLeft: 20, margin: '8px 0' }}>
          {listItems.map((item, idx) => (
            <li key={idx} style={{ marginBottom: 4 }}>
              {renderInlineStyles(item)}
            </li>
          ))}
        </ul>,
      );
      listItems = [];
    }
  };

  const renderInlineStyles = (text: string) => {
    const parts: (string | JSX.Element)[] = [];
    let remaining = text;
    let inlineKey = 0;

    while (remaining.length > 0) {
      const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
      const italicMatch = remaining.match(/\*(.+?)\*/);

      const boldIndex = boldMatch ? remaining.indexOf(boldMatch[0]) : Infinity;
      const italicIndex = italicMatch ? remaining.indexOf(italicMatch[0]) : Infinity;

      if (boldIndex === Infinity && italicIndex === Infinity) {
        parts.push(remaining);
        break;
      }

      if (boldIndex < italicIndex && boldMatch) {
        if (boldIndex > 0) {
          parts.push(remaining.slice(0, boldIndex));
        }
        parts.push(
          <strong key={`b-${inlineKey++}`} style={{ fontWeight: 600 }}>
            {boldMatch[1]}
          </strong>,
        );
        remaining = remaining.slice(boldIndex + boldMatch[0].length);
      } else if (italicMatch) {
        if (italicIndex > 0) {
          parts.push(remaining.slice(0, italicIndex));
        }
        parts.push(
          <em key={`i-${inlineKey++}`}>{italicMatch[1]}</em>,
        );
        remaining = remaining.slice(italicIndex + italicMatch[0].length);
      }
    }

    return <>{parts}</>;
  };

  lines.forEach((line) => {
    const listMatch = line.match(/^[-*]\s+(.+)$/);
    if (listMatch) {
      listItems.push(listMatch[1]);
      return;
    }
    flushList();

    if (line.startsWith('### ')) {
      elements.push(
        <Title key={`h-${keyCounter++}`} level={5} style={{ marginTop: 16, marginBottom: 8 }}>
          {renderInlineStyles(line.slice(4))}
        </Title>,
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <Title key={`h-${keyCounter++}`} level={4} style={{ marginTop: 16, marginBottom: 8 }}>
          {renderInlineStyles(line.slice(3))}
        </Title>,
      );
    } else if (line.trim() === '') {
      elements.push(<div key={`br-${keyCounter++}`} style={{ height: 8 }} />);
    } else {
      elements.push(
        <Paragraph key={`p-${keyCounter++}`} style={{ marginBottom: 8 }}>
          {renderInlineStyles(line)}
        </Paragraph>,
      );
    }
  });

  flushList();
  return <>{elements}</>;
};

const AiPage = () => {
  const queryClient = useQueryClient();
  const chatContainerRef = useRef<HTMLDivElement>(null);

  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [currentMode, setCurrentMode] = useState<AiMode>('general');
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [signalModalOpen, setSignalModalOpen] = useState(false);
  const [signalForm] = Form.useForm<SignalRequest>();

  const { data: conversations, isLoading: conversationsLoading } = useQuery({
    queryKey: ['ai', 'conversations'],
    queryFn: () => aiApi.getConversations(),
  });

  const createConversationMutation = useMutation({
    mutationFn: (mode: AiMode) =>
      aiApi.createConversation({
        mode,
        title: `${MODE_LABEL_MAP[mode]} - ${dayjs().format('MM-DD HH:mm')}`,
      }),
    onSuccess: (conv) => {
      queryClient.invalidateQueries({ queryKey: ['ai', 'conversations'] });
      setCurrentConversationId(conv.id);
      setMessages([]);
    },
  });

  const deleteConversationMutation = useMutation({
    mutationFn: (id: string) => aiApi.deleteConversation(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['ai', 'conversations'] });
      if (currentConversationId === deletedId) {
        setCurrentConversationId(null);
        setMessages([]);
      }
      message.success('会话已删除');
    },
  });

  const loadHistoryMutation = useMutation({
    mutationFn: (id: string) => aiApi.getHistory(id),
    onSuccess: (data) => {
      setMessages(data);
    },
  });

  const chatMutation = useMutation({
    mutationFn: (params: { conversation_id: string; message: string; mode: AiMode }) =>
      aiApi.chat({
        conversation_id: params.conversation_id,
        message: params.message,
        mode: params.mode,
      }),
    onMutate: () => {
      setIsGenerating(true);
    },
    onSuccess: (data) => {
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== '__loading__');
        return [...filtered, data.user_message, data.assistant_message];
      });
    },
    onError: () => {
      setMessages((prev) => prev.filter((m) => m.id !== '__loading__'));
      message.error('发送失败，请重试');
    },
    onSettled: () => {
      setIsGenerating(false);
    },
  });

  const generateSignalMutation = useMutation({
    mutationFn: (data: SignalRequest) => aiApi.generateSignal(data),
    onSuccess: (signal) => {
      setSignals((prev) => [signal, ...prev].slice(0, 5));
      setSignalModalOpen(false);
      signalForm.resetFields();
      message.success('交易信号生成成功');
    },
    onError: () => {
      message.error('信号生成失败');
    },
  });

  const generateReportMutation = useMutation({
    mutationFn: (period: ReportPeriod) => aiApi.generateReport({ period }),
    onSuccess: (report) => {
      const reportMessage: AiMessage = {
        id: `report-${Date.now()}`,
        conversation_id: currentConversationId || '',
        role: 'assistant',
        content: `## ${report.title}\n\n${report.summary || ''}\n\n${
          report.key_points ? report.key_points.map((p) => `- ${p}`).join('\n') : ''
        }\n\n${report.content || ''}`,
        created_at: report.generated_at,
      };
      setMessages((prev) => [...prev, reportMessage]);
      message.success('报告生成成功');
    },
    onError: () => {
      message.error('报告生成失败');
    },
  });

  const sortedConversations = useMemo(() => {
    return [...(conversations || [])].sort((a, b) => {
      const aTime = a.last_message_at || a.created_at;
      const bTime = b.last_message_at || b.created_at;
      return dayjs(bTime).valueOf() - dayjs(aTime).valueOf();
    });
  }, [conversations]);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  const handleCreateConversation = async () => {
    await createConversationMutation.mutateAsync(currentMode);
  };

  const handleSelectConversation = (conv: AiConversation) => {
    setCurrentConversationId(conv.id);
    setCurrentMode(conv.mode);
    loadHistoryMutation.mutate(conv.id);
  };

  const handleDeleteConversation = async (id: string) => {
    await deleteConversationMutation.mutateAsync(id);
  };

  const handleSend = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || isGenerating) return;

    let convId = currentConversationId;
    if (!convId) {
      const conv = await createConversationMutation.mutateAsync(currentMode);
      convId = conv.id;
    }

    const loadingMessage: AiMessage = {
      id: '__loading__',
      conversation_id: convId,
      role: 'assistant',
      content: 'loading',
      created_at: new Date().toISOString(),
    };

    const userMessage: AiMessage = {
      id: `user-${Date.now()}`,
      conversation_id: convId,
      role: 'user',
      content: trimmed,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage, loadingMessage]);
    setInputValue('');
    setIsGenerating(true);

    chatMutation.mutate({
      conversation_id: convId,
      message: trimmed,
      mode: currentMode,
    });
  };

  const handleStopGenerate = () => {
    setIsGenerating(false);
    setMessages((prev) => prev.filter((m) => m.id !== '__loading__'));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleGenerateSignal = () => {
    signalForm.validateFields().then((values) => {
      generateSignalMutation.mutate(values);
    });
  };

  const reportMenuItems: MenuProps['items'] = REPORT_PERIOD_OPTIONS.map((opt) => ({
    key: opt.key,
    label: opt.label,
    onClick: () => {
      generateReportMutation.mutate(opt.key as ReportPeriod);
    },
  }));

  const formatTime = (iso?: string) => {
    if (!iso) return '-';
    const d = dayjs(iso);
    const now = dayjs();
    if (d.isSame(now, 'day')) return d.format('HH:mm');
    if (d.isSame(now.subtract(1, 'day'), 'day')) return `昨天 ${d.format('HH:mm')}`;
    if (d.isSame(now, 'week')) return d.format('MM-DD HH:mm');
    return d.format('MM-DD');
  };

  return (
    <PageContainer
      title="AI 助手"
      description="智能对话分析，辅助交易决策"
      card={false}
      padding={16}
    >
      <Row gutter={[16, 0]} style={{ height: 'calc(100vh - 180px)', minHeight: 600 }}>
        {/* 左侧面板 - 会话列表 */}
        <Col span={6}>
          <Card
            styles={{ body: { padding: 16, height: '100%', display: 'flex', flexDirection: 'column' } }}
            style={{
              height: '100%',
              background: '#141414',
              border: 'none',
            }}
          >
            <Button
              type="primary"
              block
              icon={<RocketOutlined />}
              onClick={handleCreateConversation}
              loading={createConversationMutation.isPending}
              style={{ marginBottom: 16 }}
            >
              新建会话
            </Button>

            <div style={{ flex: 1, overflow: 'auto', margin: '0 -16px', padding: '0 16px' }}>
              {conversationsLoading ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
                  <Spin />
                </div>
              ) : sortedConversations.length === 0 ? (
                <EmptyState
                  description="暂无会话"
                  height={200}
                  image={EmptyState.PRESENTED_IMAGE_SIMPLE}
                />
              ) : (
                <List
                  dataSource={sortedConversations}
                  renderItem={(conv) => {
                    const isActive = currentConversationId === conv.id;
                    return (
                      <List.Item
                        key={conv.id}
                        onClick={() => handleSelectConversation(conv)}
                        style={{
                          cursor: 'pointer',
                          padding: '12px 12px',
                          marginBottom: 8,
                          borderRadius: 8,
                          background: isActive ? 'rgba(22, 119, 255, 0.15)' : 'rgba(255,255,255,0.04)',
                          border: isActive ? '1px solid #1677ff33' : '1px solid transparent',
                          transition: 'all 0.2s',
                          display: 'block',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'flex-start',
                            marginBottom: 6,
                          }}
                        >
                          <Text
                            ellipsis={{ tooltip: conv.title || '新会话' }}
                            style={{
                              color: isActive ? '#fff' : 'rgba(255,255,255,0.85)',
                              fontWeight: 500,
                              flex: 1,
                              marginRight: 8,
                            }}
                          >
                            {conv.title || '新会话'}
                          </Text>
                          <ConfirmButton
                            label={<DeleteOutlined />}
                            title="确认删除会话？"
                            description="删除后将无法恢复该会话的消息记录"
                            onConfirm={async () => handleDeleteConversation(conv.id)}
                            size="small"
                            danger
                            type="text"
                            popconfirmProps={{
                              onClick: (e) => e.stopPropagation(),
                            }}
                          />
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Tag
                            color={MODE_COLOR_MAP[conv.mode]}
                            style={{ margin: 0, borderRadius: 4 }}
                          >
                            {MODE_LABEL_MAP[conv.mode]}
                          </Tag>
                          <Text style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12 }}>
                            {formatTime(conv.last_message_at)}
                          </Text>
                        </div>
                      </List.Item>
                    );
                  }}
                />
              )}
            </div>
          </Card>
        </Col>

        {/* 右侧主聊天区域 */}
        <Col span={18} style={{ display: 'flex', flexDirection: 'column' }}>
          <Card
            styles={{ body: { padding: 0, height: '100%', display: 'flex', flexDirection: 'column' } }}
            style={{ height: '100%' }}
          >
            {/* 顶部工具栏 */}
            <div
              style={{
                padding: '12px 24px',
                borderBottom: '1px solid #f0f0f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Segmented
                value={currentMode}
                onChange={(v) => setCurrentMode(v as AiMode)}
                options={MODE_OPTIONS.map((m) => ({ label: m.label, value: m.value }))}
              />
              <Space>
                <Button
                  icon={<RocketOutlined />}
                  onClick={() => setSignalModalOpen(true)}
                >
                  生成信号
                </Button>
                <Dropdown menu={{ items: reportMenuItems }} placement="bottomRight">
                  <Button icon={<FileTextOutlined />}>
                    生成报告
                  </Button>
                </Dropdown>
              </Space>
            </div>

            {/* 信号卡片区域 */}
            {signals.length > 0 && (
              <div
                style={{
                  padding: '12px 24px',
                  borderBottom: '1px solid #f0f0f0',
                  background: '#fafafa',
                }}
              >
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  {signals.map((signal, idx) => (
                    <Card
                      key={idx}
                      size="small"
                      style={{ borderRadius: 8 }}
                      styles={{ body: { padding: 16 } }}
                    >
                      <Row gutter={16} align="middle">
                        <Col span={4}>
                          <Space direction="vertical" size={4}>
                            <Text strong style={{ fontSize: 16 }}>
                              {signal.symbol}
                            </Text>
                            <Tag
                              color={SIDE_COLOR_MAP[signal.side]}
                              style={{ margin: 0 }}
                            >
                              {SIDE_LABEL_MAP[signal.side]}
                            </Tag>
                          </Space>
                        </Col>
                        <Col span={14}>
                          <Row gutter={16}>
                            <Col span={8}>
                              <Text type="secondary" style={{ fontSize: 12 }}>入场价</Text>
                              <div style={{ fontWeight: 500 }}>
                                {signal.entry_price?.toFixed(4) || '-'}
                              </div>
                            </Col>
                            <Col span={8}>
                              <Text type="secondary" style={{ fontSize: 12 }}>止损</Text>
                              <div style={{ fontWeight: 500, color: '#ff4d4f' }}>
                                {signal.stop_loss?.toFixed(4) || '-'}
                              </div>
                            </Col>
                            <Col span={8}>
                              <Text type="secondary" style={{ fontSize: 12 }}>止盈</Text>
                              <div style={{ fontWeight: 500, color: '#52c41a' }}>
                                {signal.take_profit?.toFixed(4) || '-'}
                              </div>
                            </Col>
                          </Row>
                        </Col>
                        <Col span={6}>
                          <div style={{ marginBottom: 8 }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              置信度 {signal.confidence || 0}%
                            </Text>
                            <Progress
                              percent={signal.confidence || 0}
                              size="small"
                              showInfo={false}
                              status={
                                signal.confidence
                                  ? signal.confidence >= 70
                                    ? 'success'
                                    : signal.confidence >= 40
                                      ? 'active'
                                      : 'exception'
                                  : 'normal'
                              }
                            />
                          </div>
                          <Paragraph
                            ellipsis={{ rows: 2, tooltip: signal.reason }}
                            style={{ margin: 0, fontSize: 12, color: '#595959' }}
                          >
                            {signal.reason}
                          </Paragraph>
                        </Col>
                      </Row>
                    </Card>
                  ))}
                </Space>
              </div>
            )}

            {/* 聊天消息区域 */}
            <div
              ref={chatContainerRef}
              style={{
                flex: 1,
                overflow: 'auto',
                padding: '24px 32px',
                background: '#f5f5f5',
              }}
            >
              {messages.length === 0 ? (
                <EmptyState
                  description="开始对话，探索 AI 的智能交易分析"
                  height={400}
                  action={currentConversationId ? undefined : {
                    label: '新建会话开始对话',
                    onClick: handleCreateConversation,
                  }}
                  extra={
                    <Space direction="vertical" size={8} style={{ marginTop: 24 }}>
                      <Tag color="blue">💡 尝试：分析 BTC 的近期走势</Tag>
                      <Tag color="cyan">📊 尝试：给我一套网格交易策略建议</Tag>
                      <Tag color="purple">⚠️ 尝试：评估当前持仓的风险</Tag>
                    </Space>
                  }
                />
              ) : (
                <Space direction="vertical" size={20} style={{ width: '100%' }}>
                  {messages.map((msg) => {
                    const isUser = msg.role === 'user';
                    const isLoading = msg.id === '__loading__';

                    return (
                      <div
                        key={msg.id}
                        style={{
                          display: 'flex',
                          justifyContent: isUser ? 'flex-end' : 'flex-start',
                        }}
                      >
                        <div
                          style={{
                            maxWidth: '75%',
                            padding: '12px 16px',
                            borderRadius: isUser
                              ? '12px 12px 2px 12px'
                              : '12px 12px 12px 2px',
                            background: isUser ? '#1677ff' : '#ffffff',
                            color: isUser ? '#ffffff' : 'rgba(0,0,0,0.85)',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                            wordBreak: 'break-word',
                          }}
                        >
                          {isLoading ? (
                            <Space size={4}>
                              <Spin size="small" />
                              <Text style={{ color: 'rgba(0,0,0,0.45)' }}>
                                AI 正在思考中...
                              </Text>
                            </Space>
                          ) : isUser ? (
                            <Text style={{ color: '#fff', whiteSpace: 'pre-wrap' }}>
                              {msg.content}
                            </Text>
                          ) : (
                            renderMarkdownContent(msg.content)
                          )}
                        </div>
                      </div>
                    );
                  })}
                </Space>
              )}
            </div>

            {/* 底部输入区 */}
            <div
              style={{
                padding: '16px 24px',
                borderTop: '1px solid #f0f0f0',
                background: '#fff',
              }}
            >
              <Space.Compact style={{ width: '100%' }}>
                <TextArea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="输入消息，Enter 发送，Shift+Enter 换行..."
                  autoSize={{ minRows: 2, maxRows: 4 }}
                  disabled={isGenerating}
                  style={{
                    borderRadius: '8px 0 0 8px',
                    resize: 'none',
                  }}
                />
                {isGenerating ? (
                  <Button
                    danger
                    icon={<StopOutlined />}
                    onClick={handleStopGenerate}
                    style={{
                      height: 'auto',
                      minHeight: 66,
                      borderRadius: '0 8px 8px 0',
                      padding: '0 20px',
                    }}
                  >
                    停止生成
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={handleSend}
                    disabled={!inputValue.trim() || chatMutation.isPending}
                    loading={chatMutation.isPending}
                    style={{
                      height: 'auto',
                      minHeight: 66,
                      borderRadius: '0 8px 8px 0',
                      padding: '0 20px',
                    }}
                  >
                    发送
                  </Button>
                )}
              </Space.Compact>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 生成信号 Modal */}
      <Modal
        title={<Space><RocketOutlined />生成交易信号</Space>}
        open={signalModalOpen}
        onCancel={() => {
          setSignalModalOpen(false);
          signalForm.resetFields();
        }}
        onOk={handleGenerateSignal}
        confirmLoading={generateSignalMutation.isPending}
        okText="生成"
        cancelText="取消"
        width={560}
      >
        <Form
          form={signalForm}
          layout="vertical"
          initialValues={{ timeframe: '1h', strategy_type: 'trend_following' }}
        >
          <Form.Item
            name="symbols"
            label="交易对"
            rules={[{ required: true, message: '请选择至少一个交易对' }]}
          >
            <Select
              mode="multiple"
              placeholder="选择交易对"
              options={SYMBOL_OPTIONS}
              maxTagCount={3}
              allowClear
            />
          </Form.Item>
          <Form.Item
            name="strategy_type"
            label="策略类型"
            rules={[{ required: true, message: '请选择策略类型' }]}
          >
            <Select
              placeholder="选择策略类型"
              options={STRATEGY_OPTIONS}
            />
          </Form.Item>
          <Form.Item
            name="timeframe"
            label="时间周期"
            rules={[{ required: true, message: '请选择时间周期' }]}
          >
            <Select
              placeholder="选择时间周期"
              options={TIMEFRAME_OPTIONS}
            />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
};

export default AiPage;
