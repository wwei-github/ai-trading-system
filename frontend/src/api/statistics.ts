import dayjs from 'dayjs';
import type {
  OverviewData,
  ProfitTrendPoint,
  ProfitTrendParams,
  AssetDistributionItem,
  TradeStatsData,
  CoinRankingItem,
  MonthlyReportItem,
  WinRateTrendPoint,
  DrawdownPoint,
  ProfitDistributionItem,
  StatsQueryParams,
} from '@/types';
import { mockDelay, randomAmount } from '@/utils/mock';

// ========== Mock 数据生成 ==========
const COINS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'LINK', 'AVAX', 'DOT'];

/** 概览数据 */
const genOverview = (): OverviewData => {
  const total_asset = randomAmount(200000, 500000);
  const total_profit = randomAmount(-20000, 80000);
  return {
    total_asset,
    available_balance: Number((total_asset * 0.35).toFixed(2)),
    frozen_balance: Number((total_asset * 0.05).toFixed(2)),
    today_profit: randomAmount(-3000, 5000),
    total_profit,
    today_trade_count: 12 + Math.floor(Math.random() * 40),
    today_trade_amount: randomAmount(20000, 150000),
    active_coin_count: 6 + Math.floor(Math.random() * 5),
    win_rate: 0.45 + Math.random() * 0.3,
  };
};

/** 收益趋势 */
const genProfitTrend = (range: ProfitTrendParams['range'] = '30d'): ProfitTrendPoint[] => {
  const days = range === '7d' ? 7 : range === '30d' ? 30 : range === '90d' ? 90 : range === '1y' ? 365 : 30;
  let asset = randomAmount(180000, 220000);
  const initAsset = asset;
  return Array.from({ length: days }, (_, i) => {
    const delta = randomAmount(-asset * 0.03, asset * 0.04);
    asset = Math.max(0, asset + delta);
    const profit = asset - initAsset;
    return {
      date: dayjs().subtract(days - i - 1, 'day').format('YYYY-MM-DD'),
      total_asset: Number(asset.toFixed(2)),
      profit: Number(profit.toFixed(2)),
      profit_rate: Number(((profit / initAsset) * 100).toFixed(2)),
    };
  });
};

/** 资产分布 */
const genAssetDistribution = (): AssetDistributionItem[] => {
  const items = COINS.slice(0, 6).map((coin) => ({
    name: coin,
    value: randomAmount(5000, 80000),
    percentage: 0,
  }));
  const total = items.reduce((s, i) => s + i.value, 0);
  items.forEach((i) => (i.percentage = Number(((i.value / total) * 100).toFixed(2))));
  return items;
};

/** 交易统计 */
const genTradeStats = (): TradeStatsData => {
  const buyCount = 30 + Math.floor(Math.random() * 80);
  const sellCount = 25 + Math.floor(Math.random() * 75);
  return {
    buy_count: buyCount,
    sell_count: sellCount,
    buy_amount: randomAmount(200000, 500000),
    sell_amount: randomAmount(180000, 520000),
    symbol_stats: COINS.slice(0, 5).map((s) => ({
      symbol: s,
      count: 10 + Math.floor(Math.random() * 50),
      amount: randomAmount(10000, 150000),
    })),
  };
};

/** 币种排行 */
const genCoinRanking = (): CoinRankingItem[] => {
  return COINS.map((coin) => {
    const profit = randomAmount(-5000, 25000);
    const count = 8 + Math.floor(Math.random() * 60);
    return {
      symbol: coin,
      total_profit: profit,
      trade_count: count,
      win_rate: 0.4 + Math.random() * 0.45,
      profit_rate: Number((Math.random() * 60 - 15).toFixed(2)),
    };
  }).sort((a, b) => b.total_profit - a.total_profit);
};

/** 月度报表 */
const genMonthlyReport = (): MonthlyReportItem[] => {
  return Array.from({ length: 12 }, (_, i) => {
    const month = dayjs().subtract(11 - i, 'month').format('YYYY-MM');
    return {
      month,
      profit: randomAmount(-8000, 20000),
      trade_count: 30 + Math.floor(Math.random() * 100),
      win_rate: 0.4 + Math.random() * 0.4,
    };
  });
};

/** 胜率走势 */
const genWinRateTrend = (): WinRateTrendPoint[] => {
  return Array.from({ length: 30 }, (_, i) => ({
    date: dayjs().subtract(29 - i, 'day').format('MM-DD'),
    win_rate: 0.4 + Math.random() * 0.45,
    trade_count: 1 + Math.floor(Math.random() * 20),
  }));
};

/** 回撤曲线 */
const genDrawdown = (): DrawdownPoint[] => {
  let peak = 0;
  let maxDd = 0;
  const trend = genProfitTrend('90d');
  return trend.map((p) => {
    peak = Math.max(peak, p.total_asset);
    const dd = peak === 0 ? 0 : ((peak - p.total_asset) / peak) * -100;
    maxDd = Math.min(maxDd, dd);
    return {
      date: p.date,
      drawdown: Number(dd.toFixed(2)),
      max_drawdown: Number(maxDd.toFixed(2)),
    };
  });
};

/** 盈亏分布 */
const genProfitDist = (): ProfitDistributionItem[] => {
  const ranges = ['<-20%', '-20%~-10%', '-10%~0%', '0%~10%', '10%~20%', '>20%'];
  const counts = [3, 8, 25, 35, 18, 6];
  return ranges.map((r, i) => ({ range: r, count: counts[i] + Math.floor(Math.random() * 6) }));
};

// ========== API 方法 ==========
export const statisticsApi = {
  /** 核心概览指标 */
  async getOverview(_params: StatsQueryParams = {}): Promise<OverviewData> {
    return mockDelay(genOverview());
  },

  /** 收益趋势 */
  async getProfitTrend(params: ProfitTrendParams = {}): Promise<ProfitTrendPoint[]> {
    return mockDelay(genProfitTrend(params.range));
  },

  /** 资产分布 */
  async getAssetDistribution(_params: StatsQueryParams = {}): Promise<AssetDistributionItem[]> {
    return mockDelay(genAssetDistribution());
  },

  /** 交易统计 */
  async getTradeStats(_params: StatsQueryParams = {}): Promise<TradeStatsData> {
    return mockDelay(genTradeStats());
  },

  /** 币种盈亏排行 */
  async getCoinRanking(_params: StatsQueryParams = {}): Promise<CoinRankingItem[]> {
    return mockDelay(genCoinRanking());
  },

  /** 月度盈亏汇总 */
  async getMonthlyReport(_params: StatsQueryParams = {}): Promise<MonthlyReportItem[]> {
    return mockDelay(genMonthlyReport());
  },

  /** 胜率走势 */
  async getWinRateTrend(_params: StatsQueryParams = {}): Promise<WinRateTrendPoint[]> {
    return mockDelay(genWinRateTrend());
  },

  /** 回撤曲线 */
  async getDrawdown(_params: StatsQueryParams = {}): Promise<DrawdownPoint[]> {
    return mockDelay(genDrawdown());
  },

  /** 盈亏分布直方图 */
  async getProfitDist(_params: StatsQueryParams = {}): Promise<ProfitDistributionItem[]> {
    return mockDelay(genProfitDist());
  },

  /** 导出报表（mock blob） */
  async exportReport(_params: StatsQueryParams = {}): Promise<Blob> {
    return mockDelay(
      new Blob(['统计报表\n期间,收益,胜率,交易笔数\n2026-08,+5230.00,58%,162\n'], {
        type: 'text/csv;charset=utf-8',
      }),
      800,
    );
  },
};

export default statisticsApi;
