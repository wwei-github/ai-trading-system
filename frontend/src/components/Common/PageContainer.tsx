import { Breadcrumb, Typography, Space } from 'antd';
import type { ReactNode } from 'react';

const { Title } = Typography;

export interface PageContainerProps {
  /** 页面标题 */
  title?: string;
  /** 面包屑路径（不含首页，首页自动补全） */
  breadcrumbs?: Array<{ title: string; onClick?: () => void }>;
  /** 标题右侧操作区（与标题同一行） */
  extra?: ReactNode;
  /** 副标题或描述 */
  description?: ReactNode;
  /** 标签页或其他顶部内容（位于标题下方、内容上方） */
  subHeader?: ReactNode;
  /** 页面主体内容 */
  children?: ReactNode;
  /** 是否显示卡片包装（默认 true，为内容添加白色卡片背景） */
  card?: boolean;
  /** 自定义 content style */
  contentStyle?: React.CSSProperties;
  /** 自定义容器 padding */
  padding?: number | string;
}

const PageContainer = ({
  title,
  breadcrumbs,
  extra,
  description,
  subHeader,
  children,
  card = true,
  contentStyle,
  padding = 0,
}: PageContainerProps) => {
  const defaultBreadcrumbs: Array<{ title: string; onClick?: () => void }> = [{ title: '工作台' }];
  const allBreadcrumbs = breadcrumbs ? [...defaultBreadcrumbs, ...breadcrumbs] : defaultBreadcrumbs;

  return (
    <div style={{ padding }}>
      {/* 面包屑 */}
      <Breadcrumb
        style={{ marginBottom: title || extra ? 12 : 16 }}
        items={allBreadcrumbs.map((b) =>
          b.onClick
            ? {
                title: b.title,
                onClick: b.onClick,
              }
            : { title: b.title }
        )}
      />

      {/* 标题与操作区 */}
      {(title || extra) && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-end',
            marginBottom: subHeader || children ? 16 : 0,
          }}
        >
          <div>
            {title && (
              <Title level={4} style={{ margin: 0 }}>
                {title}
              </Title>
            )}
            {description && (
              <Space style={{ marginTop: 8, color: '#8c8c8c', fontSize: 13 }}>
                {description}
              </Space>
            )}
          </div>
          {extra && <Space>{extra}</Space>}
        </div>
      )}

      {/* Sub Header */}
      {subHeader && <div style={{ marginBottom: children ? 16 : 0 }}>{subHeader}</div>}

      {/* 主体内容 */}
      {card ? (
        <div
          style={{
            background: '#fff',
            borderRadius: 8,
            padding: 24,
            minHeight: 200,
            ...contentStyle,
          }}
        >
          {children}
        </div>
      ) : (
        children
      )}
    </div>
  );
};

export default PageContainer;
