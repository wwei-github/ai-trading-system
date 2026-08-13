import type { CSSProperties } from 'react';
import { useSettingsStore } from '@/store';

export interface AmountTextProps {
  /** 金额值 */
  value: number | string;
  /** 小数精度，默认取全局设置 */
  precision?: number;
  /** 是否根据正负显示颜色 */
  colored?: boolean;
  /** 正数颜色（默认涨绿） */
  positiveColor?: string;
  /** 负数颜色（默认跌红） */
  negativeColor?: string;
  /** 前缀符号，如 $、￥ */
  prefix?: string;
  /** 后缀，如 USDT、% */
  suffix?: string;
  /** 显示千分位分隔符，默认 true */
  thousand?: boolean;
  /** 始终显示 +/- 号 */
  showSign?: boolean;
  /** 字体大小 */
  fontSize?: number | string;
  /** 字重 */
  fontWeight?: number | string;
  /** 自定义样式 */
  style?: CSSProperties;
  /** 占位文本，当 value 为 null/undefined 时显示 */
  placeholder?: string;
  /** className */
  className?: string;
}

const AmountText = ({
  value,
  precision,
  colored = false,
  positiveColor = '#52c41a',
  negativeColor = '#ff4d4f',
  prefix,
  suffix,
  thousand = true,
  showSign = false,
  fontSize,
  fontWeight,
  style,
  placeholder = '-',
  className,
}: AmountTextProps) => {
  const { pricePrecision } = useSettingsStore();
  const displayPrecision = precision ?? pricePrecision;

  // 空值处理
  if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) {
    return <span className={className} style={{ color: '#bfbfbf', ...style }}>{placeholder}</span>;
  }

  const numValue = Number(value);
  const isPositive = numValue > 0;
  const isNegative = numValue < 0;

  // 格式化数值
  const formatOptions: Intl.NumberFormatOptions = {
    minimumFractionDigits: displayPrecision,
    maximumFractionDigits: displayPrecision,
    useGrouping: thousand,
  };

  let formatted = Math.abs(numValue).toLocaleString('zh-CN', formatOptions);

  // 加 +/- 号
  if (showSign && isPositive) {
    formatted = `+${formatted}`;
  } else if (isNegative) {
    formatted = `-${formatted}`;
  }

  // 前缀后缀
  const fullText = `${prefix ?? ''}${formatted}${suffix ?? ''}`;

  // 颜色
  let color: string | undefined;
  if (colored) {
    if (isPositive) color = positiveColor;
    else if (isNegative) color = negativeColor;
  }

  return (
    <span
      className={className}
      style={{
        color,
        fontSize,
        fontWeight,
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
        fontVariantNumeric: 'tabular-nums',
        ...style,
      }}
    >
      {fullText}
    </span>
  );
};

export default AmountText;
