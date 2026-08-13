import { create } from 'zustand';

// 应用全局状态
interface AppState {
  /** 侧边栏是否折叠 */
  collapsed: boolean;
  /** 切换侧边栏折叠状态 */
  toggleCollapsed: () => void;
  /** 设置侧边栏折叠状态 */
  setCollapsed: (collapsed: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  collapsed: false,
  toggleCollapsed: () => set((state) => ({ collapsed: !state.collapsed })),
  setCollapsed: (collapsed) => set({ collapsed }),
}));
