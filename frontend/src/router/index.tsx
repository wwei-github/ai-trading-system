import { Suspense, lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import MainLayout from '@/components/Layout/MainLayout';
import NotFoundPage from '@/pages/not-found';

const DashboardPage = lazy(() => import('@/pages/dashboard'));
const AccountsPage = lazy(() => import('@/pages/accounts'));
const TradesPage = lazy(() => import('@/pages/trades'));
const StatisticsPage = lazy(() => import('@/pages/statistics'));
const CoinsPage = lazy(() => import('@/pages/coins'));
const StrategiesPage = lazy(() => import('@/pages/strategies'));
const BooksPage = lazy(() => import('@/pages/books'));
const AiPage = lazy(() => import('@/pages/ai'));
const SystemPage = lazy(() => import('@/pages/system'));
const ErrorLogsPage = lazy(() => import('@/pages/error-logs'));

const SuspenseWrapper = ({ children }: { children: React.ReactNode }) => (
  <Suspense
    fallback={
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200 }}>
        <Spin size="large" />
      </div>
    }
  >
    {children}
  </Suspense>
);

// 路由配置：MainLayout 作为父路由，无需登录流程，默认重定向到 /dashboard
export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <SuspenseWrapper><DashboardPage /></SuspenseWrapper> },
      { path: 'accounts', element: <SuspenseWrapper><AccountsPage /></SuspenseWrapper> },
      { path: 'trades', element: <SuspenseWrapper><TradesPage /></SuspenseWrapper> },
      { path: 'statistics', element: <SuspenseWrapper><StatisticsPage /></SuspenseWrapper> },
      { path: 'coins', element: <SuspenseWrapper><CoinsPage /></SuspenseWrapper> },
      { path: 'strategies', element: <SuspenseWrapper><StrategiesPage /></SuspenseWrapper> },
      { path: 'books', element: <SuspenseWrapper><BooksPage /></SuspenseWrapper> },
      { path: 'ai', element: <SuspenseWrapper><AiPage /></SuspenseWrapper> },
      { path: 'system', element: <SuspenseWrapper><SystemPage /></SuspenseWrapper> },
      { path: 'error-logs', element: <SuspenseWrapper><ErrorLogsPage /></SuspenseWrapper> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);

export default router;

