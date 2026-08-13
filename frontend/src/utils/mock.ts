import dayjs from 'dayjs';
import type { ApiResponse, PaginatedResponse } from '@/types/api';

/** 模拟网络延迟（ms） */
const DEFAULT_DELAY = 300 + Math.random() * 400;

/** 统一包装成功响应 */
export const successResponse = <T>(data: T, message = 'ok'): ApiResponse<T> => ({
  code: 0,
  message,
  data,
});

/** 统一包装错误响应 */
export const errorResponse = (message: string, code = 500): ApiResponse<null> => ({
  code,
  message,
  data: null,
});

/** 模拟延迟 */
export const mockDelay = <T>(data: T, delayMs = DEFAULT_DELAY): Promise<T> =>
  new Promise((resolve) => {
    setTimeout(() => resolve(data), delayMs);
  });

/** 模拟分页 */
export const mockPaginate = <T>(
  items: T[],
  page = 1,
  page_size = 20,
): PaginatedResponse<T> => {
  const start = (page - 1) * page_size;
  const end = start + page_size;
  return {
    total: items.length,
    page,
    page_size,
    items: items.slice(start, end),
  };
};

/** 根据关键字模糊搜索对象数组 */
export const filterByKeyword = <T extends Record<string, any>>(
  items: T[],
  keyword: string,
  fields: (keyof T)[],
): T[] => {
  if (!keyword) return items;
  const kw = keyword.toLowerCase();
  return items.filter((item) =>
    fields.some((f) => {
      const v = item[f];
      return v !== null && v !== undefined && String(v).toLowerCase().includes(kw);
    }),
  );
};

/** 生成唯一 ID（前端 mock 用） */
let _mockIdCounter = 1000;
export const genMockId = (): number => ++_mockIdCounter;

/** 随机日期（近 N 天内） */
export const randomDate = (daysAgo = 30): string => {
  const d = dayjs().subtract(Math.floor(Math.random() * daysAgo), 'day');
  return d.format('YYYY-MM-DD HH:mm:ss');
};

/** 随机取数组中一个 */
export const randomPick = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];

/** 随机金额 */
export const randomAmount = (min: number, max: number, precision = 2): number =>
  Number((Math.random() * (max - min) + min).toFixed(precision));
