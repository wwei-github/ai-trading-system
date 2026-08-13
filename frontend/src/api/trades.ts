import dayjs from 'dayjs';
import type {
  Trade,
  TradeFormData,
  TradeListParams,
  TradeTag,
  PaginatedResponse,
  TradeDirection,
  BatchImportResult,
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
const SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'LINK/USDT'];
const DIRECTIONS: TradeDirection[] = ['buy', 'sell'];
const TAG_COLORS = ['blue', 'green', 'orange', 'purple', 'cyan', 'magenta'];

// 标签 Mock
let mockTags: TradeTag[] = [
  { id: 1, name: '长线', color: 'blue', created_at: randomDate(180) },
  { id: 2, name: '短线', color: 'green', created_at: randomDate(180) },
  { id: 3, name: '网格', color: 'orange', created_at: randomDate(180) },
  { id: 4, name: '定投', color: 'purple', created_at: randomDate(180) },
  { id: 5, name: '套利', color: 'cyan', created_at: randomDate(180) },
];

// 交易记录 Mock
const genMockTrade = (i: number): Trade => {
  const direction = randomPick(DIRECTIONS);
  const symbol = randomPick(SYMBOLS);
  const price =
    symbol.startsWith('BTC') ? randomAmount(40000, 70000, 2)
    : symbol.startsWith('ETH') ? randomAmount(2000, 4500, 2)
    : randomAmount(0.5, 200, 4);
  const amount = randomAmount(0.01, 500, 4);
  const total = Number((price * amount).toFixed(2));
  const fee = Number((total * 0.001).toFixed(6));
  // 模拟卖出时可能的盈亏
  const profit = direction === 'sell' ? randomAmount(-total * 0.15, total * 0.3, 2) : undefined;
  const tagCount = Math.floor(Math.random() * 3);
  const tags = Array.from(
    new Set(Array.from({ length: tagCount }, () => randomPick(mockTags))),
  );

  return {
    id: i + 1,
    account_id: (i % 5) + 1,
    account_alias: `BINANCE-主账号-${(i % 5) + 1}`,
    exchange: 'binance',
    symbol,
    direction,
    amount,
    price,
    total,
    fee,
    fee_currency: 'USDT',
    profit,
    trade_time: randomDate(90),
    tags,
    remark: direction === 'sell' && profit && profit > 0 ? '止盈平仓' : '',
    created_at: randomDate(90),
    updated_at: randomDate(30),
  };
};

let mockTrades: Trade[] = Array.from({ length: 60 }, (_, i) => genMockTrade(i)).sort(
  (a, b) => b.trade_time.localeCompare(a.trade_time),
);

// ========== API 方法 ==========
export const tradeApi = {
  /** 获取交易记录分页列表 */
  async getList(params: TradeListParams = {}): Promise<PaginatedResponse<Trade>> {
    const {
      page = 1,
      page_size = 20,
      account_id,
      symbol,
      direction,
      tag_id,
      start_time,
      end_time,
      keyword,
    } = params;
    let list = [...mockTrades];

    if (account_id) list = list.filter((t) => t.account_id === account_id);
    if (symbol) list = list.filter((t) => t.symbol === symbol || t.symbol.startsWith(symbol));
    if (direction) list = list.filter((t) => t.direction === direction);
    if (tag_id) list = list.filter((t) => t.tags?.some((tg) => tg.id === tag_id));
    if (start_time) list = list.filter((t) => t.trade_time >= start_time);
    if (end_time) list = list.filter((t) => t.trade_time <= dayjs(end_time).endOf('day').format('YYYY-MM-DD HH:mm:ss'));
    if (keyword) list = filterByKeyword(list, keyword, ['symbol', 'remark', 'account_alias']);

    list.sort((a, b) => b.trade_time.localeCompare(a.trade_time));

    return mockDelay(mockPaginate(list, page, page_size));
  },

  /** 获取交易详情 */
  async getDetail(id: number): Promise<Trade | null> {
    const item = mockTrades.find((t) => t.id === id) || null;
    return mockDelay(item);
  },

  /** 手动录入交易 */
  async create(data: TradeFormData): Promise<Trade> {
    const id = genMockId();
    const total = Number((data.price * data.amount).toFixed(2));
    // 卖出时根据 price 与当前 mock 均价估算盈亏（仅为 Mock 效果）
    const profit =
      data.direction === 'sell'
        ? Number(randomAmount(-total * 0.2, total * 0.3, 2))
        : undefined;
    const tags = data.tag_ids
      ? mockTags.filter((t) => data.tag_ids!.includes(t.id))
      : [];

    const newItem: Trade = {
      id,
      account_id: data.account_id,
      account_alias: `BINANCE-主账号-${data.account_id}`,
      exchange: 'binance',
      symbol: data.symbol,
      direction: data.direction,
      amount: data.amount,
      price: data.price,
      total,
      fee: data.fee ?? Number((total * 0.001).toFixed(6)),
      fee_currency: data.fee_currency || 'USDT',
      profit,
      trade_time: data.trade_time,
      tags,
      remark: data.remark,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    mockTrades = [newItem, ...mockTrades];
    return mockDelay(newItem);
  },

  /** 更新交易 */
  async update(id: number, data: Partial<TradeFormData>): Promise<Trade> {
    mockTrades = mockTrades.map((t) => {
      if (t.id !== id) return t;
      const total = data.price && data.amount ? Number((data.price * data.amount).toFixed(2)) : t.total;
      const tags = data.tag_ids ? mockTags.filter((tg) => data.tag_ids!.includes(tg.id)) : t.tags;
      return {
        ...t,
        ...data,
        total,
        tags,
        updated_at: new Date().toISOString(),
      };
    });
    return mockDelay(mockTrades.find((t) => t.id === id)!);
  },

  /** 删除交易 */
  async delete(id: number): Promise<void> {
    mockTrades = mockTrades.filter((t) => t.id !== id);
    return mockDelay(undefined);
  },

  /** 批量导入 */
  async batchImport(_file: File): Promise<BatchImportResult> {
    // 模拟导入结果
    const total = 30 + Math.floor(Math.random() * 20);
    const failed = Math.floor(Math.random() * 5);
    return mockDelay(
      {
        total,
        success: total - failed,
        failed,
        errors: Array.from({ length: failed }, (_, i) => ({
          row: (i + 1) * 7,
          message: randomPick(['币种代码无效', '时间格式不正确', '价格必须大于0']),
        })),
      },
      1000 + Math.random() * 1000,
    );
  },

  /** 批量导出（返回 mock 文件下载链接，前端模拟 blob） */
  async export(_params: TradeListParams): Promise<Blob> {
    return mockDelay(
      new Blob(
        ['ID,币种,方向,数量,价格,金额,手续费,盈亏,交易时间,备注\n1,BTC/USDT,buy,0.5,65000,32500,32.5,,2026-08-01 12:00:00,\n'],
        { type: 'text/csv;charset=utf-8' },
      ),
      600,
    );
  },

  /** 获取标签列表 */
  async getTags(): Promise<TradeTag[]> {
    return mockDelay([...mockTags]);
  },

  /** 创建标签 */
  async createTag(data: { name: string; color?: string }): Promise<TradeTag> {
    const newTag: TradeTag = {
      id: genMockId(),
      name: data.name,
      color: data.color || randomPick(TAG_COLORS),
      created_at: new Date().toISOString(),
    };
    mockTags = [...mockTags, newTag];
    return mockDelay(newTag);
  },

  /** 删除标签 */
  async deleteTag(id: number): Promise<void> {
    mockTags = mockTags.filter((t) => t.id !== id);
    return mockDelay(undefined);
  },
};

export default tradeApi;
