import type { ComponentType } from 'react';
import { DashboardOutlined, BankOutlined, SwapOutlined, BarChartOutlined, DotChartOutlined, ThunderboltOutlined, BookOutlined, RobotOutlined, FileTextOutlined, WarningOutlined, SettingOutlined, DeploymentUnitOutlined } from '@ant-design/icons';

// 菜单项配置
export interface MenuItemConfig {
  /** 路由路径，作为菜单 key */
  key: string;
  /** 菜单显示文本 */
  label: string;
  /** 菜单图标组件 */
  icon: ComponentType;
}

// 侧边栏菜单配置
export const menuItems: MenuItemConfig[] = [
  { key: '/dashboard', label: '工作台', icon: DashboardOutlined },
  { key: '/accounts', label: '交易所账号', icon: BankOutlined },
  { key: '/trades', label: '交易记录', icon: SwapOutlined },
  { key: '/statistics', label: '统计分析', icon: BarChartOutlined },
  { key: '/coins', label: '币种分析', icon: DotChartOutlined },
  { key: '/strategies', label: '交易系统', icon: ThunderboltOutlined },
  { key: '/books', label: '书籍学习', icon: BookOutlined },
  { key: '/ai', label: 'AI 助手', icon: RobotOutlined },
  { key: '/prompts', label: 'Prompt 模板', icon: FileTextOutlined },
  { key: '/error-logs', label: '错误日志', icon: WarningOutlined },
  { key: '/tasks', label: '后台任务', icon: DeploymentUnitOutlined },
  { key: '/system', label: '系统设置', icon: SettingOutlined },
];

// 应用标题
export const APP_TITLE = import.meta.env.VITE_APP_TITLE || 'AI 智能交易管理系统';
