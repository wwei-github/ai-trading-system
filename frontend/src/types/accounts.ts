import type { PageParams } from './api';

// 交易所类型
export type ExchangeType = 'binance' | 'okx' | 'bybit' | 'huobi' | 'kucoin' | 'other';

// 账号状态
export type AccountStatus = 'normal' | 'abnormal' | 'syncing' | 'disabled';

// 交易所账号实体（匹配后端 ExchangeAccountResponse）
export interface Account {
  id: string;
  user_id: string;
  exchange: string;
  label: string;
  permissions?: string[];
  is_testnet: boolean;
  status: string;
  last_sync_at?: string;
  created_at: string;
  updated_at: string;
}

// 新增账号表单（匹配后端 ExchangeAccountCreate）
export interface AccountCreateData {
  exchange: string;
  label: string;
  api_key: string;
  api_secret: string;
  passphrase?: string;
  permissions?: string[];
  is_testnet?: boolean;
}

// 编辑账号表单（匹配后端 ExchangeAccountUpdate）
export interface AccountUpdateData {
  label?: string;
  permissions?: string[];
  is_testnet?: boolean;
  status?: string;
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
  exchange?: string;
  status?: string;
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
export const ACCOUNT_STATUS_MAP: Record<string, { text: string; color: string }> = {
  normal: { text: '正常', color: 'success' },
  abnormal: { text: '异常', color: 'error' },
  syncing: { text: '同步中', color: 'processing' },
  disabled: { text: '已停用', color: 'default' },
};
