// AI 助手模式
export type AiMode = 'general' | 'market' | 'strategy' | 'risk' | 'tutor';

// AI 会话
export interface AiConversation {
  id: string;
  user_id: string;
  title: string | null;
  mode: AiMode;
  message_count?: number;
  last_message_at?: string;
  context?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// AI 消息角色
export type AiMessageRole = 'user' | 'assistant' | 'system';

// AI 消息
export interface AiMessage {
  id: string;
  conversation_id: string;
  role: AiMessageRole;
  content: string;
  model?: string;
  tokens?: number;
  tokens_used?: number;
  created_at: string;
}

// AI 聊天响应（用户消息 + AI 回复）
export interface AiChatResponse {
  user_message: AiMessage;
  assistant_message: AiMessage;
}

// 创建会话请求
export interface ConversationCreateData {
  title?: string;
  mode: AiMode;
  context?: Record<string, unknown>;
}

// 发送消息请求
export interface ChatRequest {
  conversation_id?: string;
  message: string;
  mode?: AiMode;
  model?: string;
  stream?: boolean;
  context?: Record<string, unknown>;
}

// 交易信号方向
export type TradingSignalSide = 'buy' | 'sell' | 'hold';

// 交易信号
export interface TradingSignal {
  symbol: string;
  side: TradingSignalSide;
  entry_price?: number;
  stop_loss?: number;
  take_profit?: number;
  confidence?: number;
  strength?: number;
  reason: string;
  timeframe?: string;
  strategy_id?: string;
  created_at?: string;
}

// 报告周期
export type ReportPeriod = 'daily' | 'weekly' | 'monthly';

// AI 分析报告
export interface AiReport {
  id?: string;
  title: string;
  period?: ReportPeriod;
  report_type?: string;
  summary?: string;
  content?: string;
  key_points?: string[];
  generated_at: string;
}

// 交易信号请求
export interface SignalRequest {
  symbols: string[];
  symbol?: string;
  strategy_type?: string;
  strategy_id?: string;
  timeframe?: string;
  context?: Record<string, unknown>;
}

// 报告参数
export interface ReportParams {
  period: ReportPeriod;
  report_type?: string;
  start_date?: string;
  end_date?: string;
  context?: Record<string, unknown>;
}
