import { useMemo } from 'react';
import { Layout, Menu, Select, message } from 'antd';
import type { MenuProps } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '@/store';
import { menuItems, APP_TITLE } from '@/utils/constants';
import { aiProviderApi } from '@/api/ai-provider';
import type { ProviderListResponse } from '@/types';

const { Header, Sider, Content } = Layout;

// 主布局：左侧菜单 + 顶栏 + 内容区
const MainLayout = () => {
  const collapsed = useAppStore((state) => state.collapsed);
  const toggleCollapsed = useAppStore((state) => state.toggleCollapsed);
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  // AI Provider 列表及当前激活
  const { data: providerData } = useQuery<ProviderListResponse>({
    queryKey: ['ai-providers'],
    queryFn: () => aiProviderApi.getProviders(),
    refetchInterval: 60000,
  });

  const activateMutation = useMutation({
    mutationFn: (id: string) => aiProviderApi.activateProvider(id),
    onSuccess: () => {
      message.success('AI Provider 切换成功');
      queryClient.invalidateQueries({ queryKey: ['ai-providers'] });
    },
  });

  const providers = providerData?.providers || [];
  const activeProvider = providers.find((p) => p.id === providerData?.active_provider_id);

  // 当前选中的菜单项（取路由路径第一段匹配）
  const selectedKey = useMemo(() => {
    const path = location.pathname;
    const match = menuItems.find((item) => path.startsWith(item.key));
    return match ? match.key : '/dashboard';
  }, [location.pathname]);

  // 将菜单配置转为 Ant Design Menu 所需结构
  const items: MenuProps['items'] = useMemo(
    () =>
      menuItems.map((item) => {
        const Icon = item.icon;
        return {
          key: item.key,
          icon: <Icon />,
          label: item.label,
        };
      }),
    [],
  );

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    navigate(key);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="dark">
        <div className="logo">
          {collapsed ? <span className="logo-icon">AI</span> : APP_TITLE}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={items}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout>
        <Header className="header">
          <span className="header-left">
            <span className="trigger" onClick={toggleCollapsed}>
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </span>
            <span className="header-title">{APP_TITLE}</span>
          </span>
          <span className="header-right">
            <div className="ai-provider-switch">
              <div className="ai-provider-switch-inner">
                <RobotOutlined className="ai-provider-icon" />
                <div className="ai-provider-info">
                  <span className="ai-provider-label">AI Provider</span>
                  <span className="ai-provider-name">
                    {activeProvider?.name || '未选择'}
                  </span>
                </div>
                <Select
                  value={activeProvider?.id || undefined}
                  loading={activateMutation.isPending}
                  onChange={(id) => activateMutation.mutate(id)}
                  placeholder="选择 AI Provider"
                  style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer' }}
                  variant="borderless"
                  popupMatchSelectWidth={260}
                  getPopupContainer={() => document.body}
                  labelRender={() => <span />}
                  options={providers.map((p) => ({
                    value: p.id,
                    label: `${p.name}  ·  ${p.config?.model || ''}`,
                    disabled: p.id === activeProvider?.id,
                  }))}
                />
              </div>
            </div>
          </span>
        </Header>
        <Content className="content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
