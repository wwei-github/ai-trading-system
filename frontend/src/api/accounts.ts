import type {
  Account,
  AccountListParams,
  AccountCreateData,
  AccountUpdateData,
  ConnectionTestResult,
  PaginatedResponse,
  ExchangeType,
  AccountStatus,
} from '@/types';
import {
  mockDelay,
  mockPaginate,
  filterByKeyword,
  genMockId,
  randomAmount,
  randomDate,
  randomPick,
} from '@/utils/mock';

// ========== Mock 数据 ==========
const EXCHANGES: ExchangeType[] = ['binance', 'okx', 'bybit', 'huobi', 'kucoin'];
const STATUSES: AccountStatus[] = ['normal', 'normal', 'normal', 'abnormal', 'syncing'];

const genMockAccount = (i: number): Account => {
  const ex = EXCHANGES[i % EXCHANGES.length];
  const total = randomAmount(1000, 100000);
  const frozen = randomAmount(0, total * 0.2);
  return {
    id: i + 1,
    exchange: ex,
    alias: `${ex.toUpperCase()}-主账号-${i + 1}`,
    api_key: `***${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
    status: randomPick(STATUSES),
    total_asset: total,
    available_balance: Number((total - frozen).toFixed(2)),
    frozen_balance: Number(frozen.toFixed(2)),
    last_sync_at: randomDate(3),
    remark: i % 3 === 0 ? '用于现货网格交易' : '',
    created_at: randomDate(180),
    updated_at: randomDate(30),
  };
};

let mockAccounts: Account[] = Array.from({ length: 12 }, (_, i) => genMockAccount(i));

// ========== API 方法 ==========
export const accountApi = {
  /** 获取账号分页列表 */
  async getList(params: AccountListParams = {}): Promise<PaginatedResponse<Account>> {
    const { page = 1, page_size = 20, exchange, status, keyword } = params;
    let list = [...mockAccounts];

    if (exchange) list = list.filter((a) => a.exchange === exchange);
    if (status) list = list.filter((a) => a.status === status);
    if (keyword) list = filterByKeyword(list, keyword, ['alias', 'api_key', 'remark']);

    list.sort((a, b) => b.updated_at.localeCompare(a.updated_at));

    return mockDelay(mockPaginate(list, page, page_size));
  },

  /** 获取账号详情 */
  async getDetail(id: number): Promise<Account | null> {
    const item = mockAccounts.find((a) => a.id === id) || null;
    return mockDelay(item);
  },

  /** 新增账号 */
  async create(data: AccountCreateData): Promise<Account> {
    const id = genMockId();
    const newItem: Account = {
      id,
      exchange: data.exchange,
      alias: data.alias,
      api_key: data.api_key ? `***${data.api_key.slice(-4)}` : '***',
      status: 'syncing',
      total_asset: 0,
      available_balance: 0,
      frozen_balance: 0,
      last_sync_at: new Date().toISOString(),
      remark: data.remark,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    mockAccounts = [newItem, ...mockAccounts];
    return mockDelay(newItem);
  },

  /** 更新账号 */
  async update(id: number, data: AccountUpdateData): Promise<Account> {
    mockAccounts = mockAccounts.map((a) =>
      a.id === id
        ? {
            ...a,
            ...data,
            api_key: data.api_key ? `***${data.api_key.slice(-4)}` : a.api_key,
            updated_at: new Date().toISOString(),
          }
        : a,
    );
    const updated = mockAccounts.find((a) => a.id === id)!;
    return mockDelay(updated);
  },

  /** 删除账号（软删除） */
  async delete(id: number): Promise<void> {
    mockAccounts = mockAccounts.filter((a) => a.id !== id);
    return mockDelay(undefined);
  },

  /** 连接测试 */
  async testConnection(_id: number): Promise<ConnectionTestResult> {
    // 5% 概率失败，模拟真实情况
    const success = Math.random() > 0.05;
    return mockDelay(
      {
        success,
        message: success ? '连接成功，API Key 有效' : '连接失败：API Key 无效或网络异常',
        latency_ms: success ? Math.floor(50 + Math.random() * 200) : undefined,
        permissions: success ? ['read', 'trade'] : undefined,
      },
      600 + Math.random() * 600,
    );
  },

  /** 同步余额 */
  async syncBalance(id: number): Promise<Account> {
    mockAccounts = mockAccounts.map((a) => {
      if (a.id !== id) return a;
      const total = randomAmount(1000, 120000);
      const frozen = randomAmount(0, total * 0.15);
      return {
        ...a,
        status: 'normal',
        total_asset: Number(total.toFixed(2)),
        available_balance: Number((total - frozen).toFixed(2)),
        frozen_balance: Number(frozen.toFixed(2)),
        last_sync_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    });
    return mockDelay(mockAccounts.find((a) => a.id === id)!, 500 + Math.random() * 500);
  },
};

export default accountApi;
