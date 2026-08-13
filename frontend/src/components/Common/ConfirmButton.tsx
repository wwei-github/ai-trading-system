import { useState } from 'react';
import { Button, Popconfirm, Tooltip } from 'antd';
import type { ButtonProps, PopconfirmProps } from 'antd';
import type { ReactNode } from 'react';

export interface ConfirmButtonProps {
  /** 点击确认后的回调，返回 Promise 会自动 loading */
  onConfirm: () => Promise<void> | void;
  /** 按钮文本 */
  label?: ReactNode;
  /** Popconfirm 标题 */
  title?: ReactNode;
  /** Popconfirm 描述 */
  description?: ReactNode;
  /** 确认按钮文本 */
  okText?: string;
  /** 取消按钮文本 */
  cancelText?: string;
  /** 按钮类型，默认 danger */
  danger?: boolean;
  /** Button type */
  type?: ButtonProps['type'];
  /** Button icon */
  icon?: ButtonProps['icon'];
  /** Button size */
  size?: ButtonProps['size'];
  /** Tooltip 提示 */
  tooltip?: string;
  /** 是否禁用 */
  disabled?: boolean;
  /** 是否直接二次确认（不通过 Popconfirm 则按钮本身是危险操作）*/
  popconfirmProps?: Omit<PopconfirmProps, 'title' | 'onConfirm' | 'okText' | 'cancelText'>;
  /** 额外 className */
  className?: string;
}

const ConfirmButton = ({
  onConfirm,
  label = '删除',
  title = '确认操作',
  description,
  okText = '确定',
  cancelText = '取消',
  danger = true,
  type = 'link',
  icon,
  size,
  tooltip,
  disabled,
  popconfirmProps,
  className,
}: ConfirmButtonProps) => {
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
    try {
      setLoading(true);
      await onConfirm();
    } finally {
      setLoading(false);
    }
  };

  const button = (
    <Button
      type={type}
      size={size}
      danger={danger}
      icon={icon}
      disabled={disabled}
      loading={loading}
      className={className}
    >
      {label}
    </Button>
  );

  const wrapped = tooltip ? <Tooltip title={tooltip}>{button}</Tooltip> : button;

  return (
    <Popconfirm
      title={title}
      description={description}
      okText={okText}
      cancelText={cancelText}
      onConfirm={handleConfirm}
      okButtonProps={{ danger }}
      disabled={disabled || loading}
      {...popconfirmProps}
    >
      {wrapped}
    </Popconfirm>
  );
};

export default ConfirmButton;
