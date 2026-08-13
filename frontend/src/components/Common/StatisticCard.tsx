import { Card, Skeleton, Tooltip } from 'antd';
import { CaretUpOutlined, CaretDownOutlined } from '@ant-design/icons';
import type { ReactNode } from 'react';
import { useSettingsStore } from '@/store';

export interface StatisticCardProps {
  /** 标题 */
  title: string;
  /** 数值 */
  value: string | number;
  /** 涨跌值/率（正数上升，负数下降） */
  delta?: number;
  /** 涨跌显示文本 */
  deltaText?: string;
  /** 前缀图标 */
  icon?: ReactNode;
  /** 前缀颜色 */
  iconBgColor?: string;
  /** 值的单位 */
  suffix?: string;
  /** 精度（用于数值格式化） */
  precision?: number;
  /** 数值是否根据正负着色（仅对 value 生效，delta 始终着色） */
  colored?: boolean;
  /** 显示 +/- 符号 */
  showSign?: boolean;
  /** loading */
  loading?: boolean;
  /** tooltip 说明 */
  tooltip?: string;
  /** 点击事件 */
  onClick?: () => void;
  /** 底部额外内容 */
  footer?: ReactNode;
}

// 格式化数字（千分位 + 精度）
const formatNumber = (value: string | number, precision = 2): string => {
  if (typeof value === 'string') return value;
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
};

const StatisticCard = ({
  title,
  value,
  delta,
  deltaText,
  icon,
  iconBgColor = '#1677ff',
  suffix,
  precision,
  colored,
  showSign,
  loading,
  tooltip,
  onClick,
  footer,
}: StatisticCardProps) => {
  const { pricePrecision } = useSettingsStore();
  const displayPrecision = precision ?? pricePrecision;

  // 判断 delta 的颜色
  const isPositive = (delta ?? 0) >= 0;
  const deltaColor = isPositive ? '#52c41a' : '#ff4d4f';

  // 主值颜色与符号
  const numValue = typeof value === 'number' ? value : 0;
  const valueColor = colored
    ? numValue >= 0
      ? '#52c41a'
      : '#ff4d4f'
    : '#1f1f1f';
  const signPrefix = showSign && numValue > 0 ? '+' : '';

  const titleNode = (
    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span>{title}</span>
      {tooltip && <Tooltip title={tooltip}>ⓘ</Tooltip>}
    </span>
  );

  return (
    <Card
      hoverable={!!onClick}
      onClick={onClick}
      style={{
        height: '100%',
        borderRadius: 12,
        transition: 'transform 0.2s, box-shadow 0.2s',
      }}
      styles={{ body: { padding: 20 } }}
    >
      <Skeleton active loading={loading} paragraph={{ rows: 3 }} title={false}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ color: '#8c8c8c', fontSize: 13, marginBottom: 10 }}>{titleNode}</div>
            <div
              style={{
                fontSize: 26,
                fontWeight: 600,
                lineHeight: 1.2,
                color: valueColor,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {signPrefix}
              {formatNumber(value, displayPrecision)}
              {suffix && <span style={{ fontSize: 14, marginLeft: 4, color: '#8c8c8c' }}>{suffix}</span>}
            </div>
          </div>
          {icon && (
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 10,
                backgroundColor: iconBgColor,
                opacity: 0.15,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  color: iconBgColor,
                  fontSize: 22,
                }}
              >
                {icon}
              </div>
            </div>
          )}
        </div>

        {(delta !== undefined || deltaText) && (
          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            {delta !== undefined && (
              <>
                {isPositive ? (
                  <CaretUpOutlined style={{ color: deltaColor, fontSize: 12 }} />
                ) : (
                  <CaretDownOutlined style={{ color: deltaColor, fontSize: 12 }} />
                )}
                <span style={{ color: deltaColor, fontSize: 13, fontWeight: 500 }}>
                  {Math.abs(delta).toLocaleString('zh-CN', {
                    minimumFractionDigits: displayPrecision,
                    maximumFractionDigits: displayPrecision,
                  })}
                  {suffix || '%'}
                </span>
              </>
            )}
            {deltaText && (
              <span style={{ color: '#8c8c8c', fontSize: 12 }}>{deltaText}</span>
            )}
          </div>
        )}

        {footer && <div style={{ marginTop: 12 }}>{footer}</div>}
      </Skeleton>
    </Card>
  );
};

export default StatisticCard;
