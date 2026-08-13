import { useMemo } from 'react';
import { Layout, Menu } from 'antd';
import type { MenuProps } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store';
import { menuItems, APP_TITLE } from '@/utils/constants';

const { Header, Sider, Content } = Layout;

// 主布局：左侧菜单 + 顶栏 + 内容区
const MainLayout = () => {
  const collapsed = useAppStore((state) => state.collapsed);
  const toggleCollapsed = useAppStore((state) => state.toggleCollapsed);
  const navigate = useNavigate();
  const location = useLocation();

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
          <span className="trigger" onClick={toggleCollapsed}>
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </span>
          {/* 主题切换预留位 */}
          <span className="header-right" />
        </Header>
        <Content className="content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
