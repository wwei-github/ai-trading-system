import { createBrowserRouter, Navigate } from 'react-router-dom';
import MainLayout from '@/components/Layout/MainLayout';
import DashboardPage from '@/pages/dashboard';
import AccountsPage from '@/pages/accounts';
import TradesPage from '@/pages/trades';
import StatisticsPage from '@/pages/statistics';
import CoinsPage from '@/pages/coins';
import StrategiesPage from '@/pages/strategies';
import BooksPage from '@/pages/books';
import AiPage from '@/pages/ai';
import SystemPage from '@/pages/system';

// 路由配置：MainLayout 作为父路由，无需登录流程，默认重定向到 /dashboard
export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'accounts', element: <AccountsPage /> },
      { path: 'trades', element: <TradesPage /> },
      { path: 'statistics', element: <StatisticsPage /> },
      { path: 'coins', element: <CoinsPage /> },
      { path: 'strategies', element: <StrategiesPage /> },
      { path: 'books', element: <BooksPage /> },
      { path: 'ai', element: <AiPage /> },
      { path: 'system', element: <SystemPage /> },
    ],
  },
]);

export default router;
