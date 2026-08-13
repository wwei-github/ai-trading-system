import type { PageParams } from './api';

// 交易所类型
export type ExchangeType = 'binance' | 'okx' | 'bybit' | 'huobi' | 'kucoin' | 'other';

// 账号状态
export type AccountStatus = 'normal' | 'abnormal' | 'syncing' | 'disabled';

// 交易所账号实体
export interface Account {
  id: number;
  exchange: ExchangeType;
  alias: string;
  api_key: string;
  status: AccountStatus;
  total_asset: number;
  available_balance: number;
  frozen_balance: number;
  last_sync_at: string;
  remark?: string;
  created_at: string;
  updated_at: string;
}

// 新增账号表单
export interface AccountCreateData {
  exchange: ExchangeType;
  alias: string;
  api_key: string;
  secret: string;
  passphrase?: string;
  remark?: string;
}

// 编辑账号表单
export interface AccountUpdateData extends Partial<Omit<AccountCreateData, 'secret'>> {
  secret?: string;
}

// 连接测试结果
export interface ConnectionTestResult {
  success: boolean;
  message: string;
  latency_ms?: number;
  permissions?: string[];
}

// 账号列表查询参数
export interface AccountListParams extends PageParams {
  exchange?: ExchangeType;
  status?: AccountStatus;
  keyword?: string;
}

// 交易所配置映射
export const EXCHANGE_OPTIONS: Array<{ value: ExchangeType; label: string; color: string }> = [
  { value: 'binance', label: '币安', color: '#F3BA2F' },
  { value: 'okx', label: 'OKX', color: '#1B1C21' },
  { value: 'bybit', label: 'Bybit', color: '#FF7A00' },
  { value: 'huobi', label: '火币', color: '#1E88E5' },
  { value: 'kucoin', label: 'KuCoin', color: '#24AE8F' },
  { value: 'other', label: '其他', color: '#8c8c8c' },
];

// 状态映射
export const ACCOUNT_STATUS_MAP: Record<AccountStatus, { text: string; color: string }> = {
  normal: { text: '正常', color: 'success' },
  abnormal: { text: '异常', color: 'error' },
  syncing: { text: '同步中', color: 'processing' },
  disabled: { text: '已停用', color: 'default' },
};
