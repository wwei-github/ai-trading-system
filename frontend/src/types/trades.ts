import type { PageParams } from './api';

// 交易方向
export type TradeDirection = 'buy' | 'sell';

// 交易标签
export interface TradeTag {
  id: number;
  name: string;
  color?: string;
  created_at: string;
}

// 交易记录实体
export interface Trade {
  id: number;
  account_id: number;
  account_alias?: string;
  exchange?: string;
  symbol: string;
  direction: TradeDirection;
  amount: number;
  price: number;
  total: number;
  fee: number;
  fee_currency?: string;
  profit?: number;
  trade_time: string;
  tags?: TradeTag[];
  remark?: string;
  created_at: string;
  updated_at: string;
}

// 新增/编辑交易表单
export interface TradeFormData {
  account_id: number;
  symbol: string;
  direction: TradeDirection;
  amount: number;
  price: number;
  fee?: number;
  fee_currency?: string;
  trade_time: string;
  tag_ids?: number[];
  remark?: string;
}

// 交易记录查询参数
export interface TradeListParams extends PageParams {
  account_id?: number;
  exchange?: string;
  symbol?: string;
  direction?: TradeDirection;
  tag_id?: number;
  start_time?: string;
  end_time?: string;
  keyword?: string;
}

// 批量导入结果
export interface BatchImportResult {
  total: number;
  success: number;
  failed: number;
  errors: Array<{ row: number; message: string }>;
}

// 方向映射
export const TRADE_DIRECTION_MAP: Record<TradeDirection, { text: string; color: string }> = {
  buy: { text: '买入', color: '#52c41a' },
  sell: { text: '卖出', color: '#ff4d4f' },
};
