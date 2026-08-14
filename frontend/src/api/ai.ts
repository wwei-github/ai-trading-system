import request from './request';
import type {
  AiConversation,
  AiMessage,
  AiChatResponse,
  ConversationCreateData,
  ChatRequest,
  TradingSignal,
  AiReport,
  SignalRequest,
  ReportParams,
} from '@/types';

export const aiApi = {
  /** 获取会话列表 */
  async getConversations(): Promise<AiConversation[]> {
    const res = await request.get<AiConversation[]>('/ai/conversations');
    return res.data;
  },

  /** 获取会话详情 */
  async getConversation(conversationId: string): Promise<AiConversation> {
    const res = await request.get<AiConversation>(`/ai/conversations/${conversationId}`);
    return res.data;
  },

  /** 获取会话消息历史 */
  async getHistory(conversationId: string): Promise<AiMessage[]> {
    const res = await request.get<AiMessage[]>(`/ai/conversations/${conversationId}/messages`);
    return res.data;
  },

  /** 创建会话 */
  async createConversation(data: ConversationCreateData): Promise<AiConversation> {
    const res = await request.post<AiConversation>('/ai/conversations', data);
    return res.data;
  },

  /** 删除会话 */
  async deleteConversation(id: string): Promise<{ deleted: boolean }> {
    const res = await request.delete<{ deleted: boolean }>(`/ai/conversations/${id}`);
    return res.data;
  },

  /** 发送消息（非流式） */
  async chat(data: ChatRequest): Promise<AiChatResponse> {
    const { conversation_id, message, context } = data;
    if (!conversation_id) {
      throw new Error('conversation_id is required for chat');
    }
    const res = await request.post<AiChatResponse>(
      `/ai/conversations/${conversation_id}/messages`,
      { content: message, context },
    );
    return res.data;
  },

  /** 流式对话（SSE） - 返回原始 Response 供 EventSource 处理 */
  async streamChat(data: ChatRequest): Promise<Response> {
    const { conversation_id, message, context } = data;
    if (!conversation_id) {
      throw new Error('conversation_id is required for streamChat');
    }
    return request.post(
      `/ai/conversations/${conversation_id}/stream`,
      { content: message, context },
      {
        responseType: 'stream',
        headers: { Accept: 'text/event-stream' },
      },
    );
  },

  /** 生成交易信号 */
  async generateSignal(data: SignalRequest): Promise<TradingSignal> {
    const payload = {
      symbol: data.symbol || data.symbols?.[0] || '',
      strategy_id: data.strategy_id,
      context: data.context,
    };
    const res = await request.post<TradingSignal>('/ai/signals/generate', payload);
    return res.data;
  },

  /** 生成分析报告 */
  async generateReport(params: ReportParams): Promise<AiReport> {
    const payload = {
      report_type: params.report_type || params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      context: params.context,
    };
    const res = await request.post<AiReport>('/ai/reports/generate', payload);
    return res.data;
  },
};

export default aiApi;
