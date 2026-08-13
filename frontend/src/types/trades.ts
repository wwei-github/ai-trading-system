import type { PageParams } from './api';

// 交易方向（匹配后端 side 字段）
export type TradeDirection = 'buy' | 'sell';

// 交易标签
export interface TradeTag {
  id: string;
  name: string;
  color?: string;
}

// 交易记录实体（匹配后端 TradeResponse）
export interface Trade {
  id: string;
  user_id: string;
  account_id: string;
  exchange: string;
  symbol: string;
  market_type: string;
  side: TradeDirection;
  direction?: TradeDirection;
  order_type: string;
  price: number;
  quantity: number;
  amount?: number;
  leverage?: number;
  fee?: number;
  fee_currency?: string;
  status: string;
  strategy_id?: string;
  tags?: string[];
  note?: string;
  remark?: string;
  total?: number;
  profit?: number;
  account_alias?: string;
  trade_time?: string;
  exchange_order_id?: string;
  executed_at: string;
  created_at: string;
}

// 新增/编辑交易表单（匹配后端 TradeImportItem）
export interface TradeFormData {
  account_id: string;
  exchange: string;
  symbol: string;
  market_type?: string;
  side: TradeDirection;
  direction?: TradeDirection;
  order_type?: string;
  price: number;
  quantity: number;
  amount?: number;
  leverage?: number;
  fee?: number;
  fee_currency?: string;
  status?: string;
  strategy_id?: string;
  tags?: string[];
  tag_ids?: string[];
  note?: string;
  remark?: string;
  exchange_order_id?: string;
  executed_at: string;
  trade_time?: string;
}

// 交易记录查询参数（匹配后端 TradeQueryParams）
export interface TradeListParams extends PageParams {
  exchange?: string;
  symbol?: string;
  side?: TradeDirection;
  direction?: TradeDirection;
  status?: string;
  strategy_id?: string;
  start_date?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  keyword?: string;
  account_id?: string;
}

// 批量导入结果（匹配后端 TradeImportResponse）
export interface BatchImportResult {
  total: number;
  imported: number;
  success?: number;
  skipped: number;
  failed?: number;
  errors: string[];
}

// 方向映射
export const TRADE_DIRECTION_MAP: Record<TradeDirection, { text: string; color: string }> = {
  buy: { text: '买入', color: '#52c41a' },
  sell: { text: '卖出', color: '#ff4d4f' },
};
