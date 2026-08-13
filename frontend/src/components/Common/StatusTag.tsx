import { Tag } from 'antd';
import type { TagProps } from 'antd';

export interface StatusTagProps<S extends string | number = string> {
  /** 当前状态值 */
  status: S;
  /** 状态映射配置 */
  mapping: Record<S, { text: string; color: TagProps['color'] }>;
  /** Tag 其他 props */
  tagProps?: Omit<TagProps, 'color'>;
}

const StatusTag = <S extends string | number>({
  status,
  mapping,
  tagProps,
}: StatusTagProps<S>) => {
  const cfg = mapping[status];

  if (!cfg) {
    return <Tag color="default" {...tagProps}>{String(status)}</Tag>;
  }

  return (
    <Tag color={cfg.color} {...tagProps}>
      {cfg.text}
    </Tag>
  );
};

export default StatusTag;
