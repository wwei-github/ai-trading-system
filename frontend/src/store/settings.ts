import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ThemeMode = 'light' | 'dark';
export type Locale = 'zh-CN' | 'en-US';

// 全局设置状态
interface SettingsState {
  /** 主题模式 */
  theme: ThemeMode;
  /** 语言 */
  locale: Locale;
  /** 默认交易所 */
  defaultExchange: string;
  /** 价格精度 */
  pricePrecision: number;
  /** 数量精度 */
  amountPrecision: number;
  /** 设置主题 */
  setTheme: (theme: ThemeMode) => void;
  /** 设置语言 */
  setLocale: (locale: Locale) => void;
  /** 设置默认交易所 */
  setDefaultExchange: (exchange: string) => void;
  /** 设置价格精度 */
  setPricePrecision: (precision: number) => void;
  /** 设置数量精度 */
  setAmountPrecision: (precision: number) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: 'light',
      locale: 'zh-CN',
      defaultExchange: '',
      pricePrecision: 2,
      amountPrecision: 4,
      setTheme: (theme) => set({ theme }),
      setLocale: (locale) => set({ locale }),
      setDefaultExchange: (exchange) => set({ defaultExchange: exchange }),
      setPricePrecision: (precision) => set({ pricePrecision: precision }),
      setAmountPrecision: (precision) => set({ amountPrecision: precision }),
    }),
    {
      name: 'settings-storage',
    },
  ),
);
