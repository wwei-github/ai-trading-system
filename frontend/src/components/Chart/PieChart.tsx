import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Spin, Empty } from 'antd';
import type { EChartsOption } from 'echarts';

export interface PieChartData {
  name: string;
  value: number;
  color?: string;
}

export interface PieChartProps {
  data: PieChartData[];
  /** loading */
  loading?: boolean;
  /** 高度 */
  height?: number | string;
  /** 标题 */
  title?: string;
  /** 显示图例（默认 true） */
  showLegend?: boolean;
  /** 是否环形（默认 true） */
  donut?: boolean;
  /** 中心文字（仅 donut 模式） */
  centerText?: string | { top: string; bottom: string };
  /** 数值后缀 */
  valueSuffix?: string;
  /** 自定义颜色调色板 */
  colors?: string[];
  /** 空数据文本 */
  emptyText?: string;
  /** 额外 option 覆盖 */
  extraOption?: Partial<EChartsOption>;
  style?: React.CSSProperties;
}

const DEFAULT_COLORS = [
  '#1677ff',
  '#52c41a',
  '#faad14',
  '#ff4d4f',
  '#722ed1',
  '#13c2c2',
  '#eb2f96',
  '#fa541c',
];

const PieChart = ({
  data,
  loading,
  height = 320,
  title,
  showLegend = true,
  donut = true,
  centerText,
  valueSuffix = '',
  colors,
  emptyText = '暂无数据',
  extraOption,
  style,
}: PieChartProps) => {
  const palette = colors || DEFAULT_COLORS;
  const isEmpty = !loading && data.length === 0;
  const total = data.reduce((s, d) => s + d.value, 0);

  const option: EChartsOption = useMemo(() => {
    const seriesData = data.map((d, i) => ({
      name: d.name,
      value: d.value,
      itemStyle: { color: d.color || palette[i % palette.length] },
    }));

    return {
      color: palette,
      title: title
        ? {
            text: title,
            left: 16,
            top: 12,
            textStyle: { fontSize: 14, fontWeight: 500, color: '#1f1f1f' },
          }
        : undefined,
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(0,0,0,0.8)',
        borderColor: 'transparent',
        textStyle: { color: '#fff' },
        formatter: (params: any) =>
          total > 0
            ? `${params.marker}${params.name}<br/>
               数值：<b>${Number(params.value).toLocaleString('zh-CN')}${valueSuffix}</b><br/>
               占比：<b>${((params.value / total) * 100).toFixed(2)}%</b>`
            : `${params.marker}${params.name}<br/>数值：<b>${params.value}${valueSuffix}</b>`,
      },
      legend: showLegend
        ? {
            type: 'scroll',
            orient: 'vertical',
            right: 12,
            top: 'center',
            icon: 'circle',
            itemWidth: 8,
            itemHeight: 8,
            textStyle: { color: '#595959', fontSize: 12 },
            formatter: (name: string) => {
              const item = data.find((d) => d.name === name);
              if (!item) return name;
              const pct = total > 0 ? ((item.value / total) * 100).toFixed(1) : '0';
              return `${name}  ${pct}%`;
            },
          }
        : undefined,
      graphic:
        donut && centerText
          ? [
              {
                type: 'text',
                left: '25%',
                top: '42%',
                style: {
                  textAlign: 'center',
                  text: typeof centerText === 'string' ? centerText : centerText.top,
                  fontSize: 18,
                  fontWeight: 600,
                  fill: '#1f1f1f',
                },
              },
              typeof centerText !== 'string' && centerText.bottom
                ? {
                    type: 'text',
                    left: '25%',
                    top: '58%',
                    style: {
                      textAlign: 'center',
                      text: centerText.bottom,
                      fontSize: 12,
                      fill: '#8c8c8c',
                    },
                  }
                : undefined,
            ].filter(Boolean)
          : undefined,
      series: [
        {
          name: title || '分布',
          type: 'pie',
          radius: donut ? ['50%', '72%'] : '65%',
          center: showLegend ? ['32%', '55%'] : ['50%', '55%'],
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: 4,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: {
            show: !showLegend,
            formatter: '{b}\n{d}%',
            fontSize: 11,
          },
          labelLine: { show: !showLegend },
          emphasis: {
            scale: true,
            scaleSize: 6,
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.2)' },
          },
          data: seriesData,
        },
      ],
      ...extraOption,
    } as EChartsOption;
  }, [data, palette, title, showLegend, donut, centerText, valueSuffix, total, extraOption]);

  if (loading) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          ...style,
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          ...style,
        }}
      >
        <Empty description={emptyText} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  return (
    <ReactECharts
      option={option}
      style={{ height, width: '100%', ...style }}
      opts={{ renderer: 'canvas' }}
      notMerge
      lazyUpdate
    />
  );
};

export default PieChart;
