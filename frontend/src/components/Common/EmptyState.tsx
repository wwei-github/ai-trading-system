import { Empty, Button } from 'antd';
import type { ReactNode } from 'react';

export interface EmptyStateProps {
  /** 标题/描述 */
  description?: ReactNode;
  /** 图片类型，可选 empty、simple 或自定义图片 */
  image?: ReactNode;
  /** 操作按钮 */
  action?: {
    label: string;
    onClick: () => void;
    type?: 'primary' | 'default' | 'dashed' | 'link' | 'text';
  };
  /** 额外内容（位于 action 下方） */
  extra?: ReactNode;
  /** 高度，用于垂直居中 */
  height?: number | string;
  /** 自定义样式 */
  style?: React.CSSProperties;
}

const EmptyState = ({
  description = '暂无数据',
  image,
  action,
  extra,
  height = 300,
  style,
}: EmptyStateProps) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: height,
        width: '100%',
        padding: 40,
        ...style,
      }}
    >
      <Empty
        image={image || Empty.PRESENTED_IMAGE_SIMPLE}
        description={<span style={{ color: '#8c8c8c' }}>{description}</span>}
      >
        {action && (
          <Button type={action.type || 'primary'} onClick={action.onClick}>
            {action.label}
          </Button>
        )}
        {extra}
      </Empty>
    </div>
  );
};

export default EmptyState;
