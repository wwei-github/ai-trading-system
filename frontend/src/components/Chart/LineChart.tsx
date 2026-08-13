import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Spin, Empty } from 'antd';
import type { EChartsOption } from 'echarts';

export interface LineChartSeries {
  name: string;
  data: number[] | Array<[string | number, number]>;
  /** 线颜色 */
  color?: string;
  /** 折线 / 阶梯 / 柱状 */
  type?: 'line' | 'bar' | 'step';
  /** 是否填充面积 */
  area?: boolean;
  /** y 轴 index，默认 0 */
  yAxisIndex?: number;
}

export interface LineChartProps {
  /** x 轴类目（当 series.data 非 [x,y] 元组时必填） */
  categories?: string[];
  /** 数据系列 */
  series: LineChartSeries[];
  /** loading */
  loading?: boolean;
  /** 高度 */
  height?: number | string;
  /** 主标题 */
  title?: string;
  /** x 轴名称 */
  xAxisName?: string;
  /** y 轴名称（单轴 string，双轴 string[]） */
  yAxisName?: string | [string, string];
  /** 是否显示图例 */
  showLegend?: boolean;
  /** 最小/最大 y 轴值 */
  yAxisMin?: number | string;
  yAxisMax?: number | string;
  /** 数值格式化后缀，如 '%' 或 ' USDT' */
  valueSuffix?: string;
  /** 自定义颜色（覆盖默认调色板） */
  colors?: string[];
  /** 空数据提示 */
  emptyText?: string;
  /** 额外的 ECharts option 覆盖 */
  extraOption?: Partial<EChartsOption>;
  /** 样式 */
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
];

const LineChart = ({
  categories,
  series,
  loading,
  height = 320,
  title,
  xAxisName,
  yAxisName,
  showLegend = true,
  yAxisMin,
  yAxisMax,
  valueSuffix = '',
  colors,
  emptyText = '暂无数据',
  extraOption,
  style,
}: LineChartProps) => {
  const palette = colors || DEFAULT_COLORS;

  const isEmpty =
    !loading &&
    (series.length === 0 ||
      series.every((s) => Array.isArray(s.data) && s.data.length === 0));

  const option: EChartsOption = useMemo(() => {
    const seriesConfig = series.map((s, idx) => {
      const color = s.color || palette[idx % palette.length];
      const chartType = s.type === 'bar' ? 'bar' : s.type === 'step' ? 'line' : 'line';
      return {
        name: s.name,
        type: chartType,
        step: s.type === 'step' ? true : undefined,
        smooth: s.type !== 'bar' && s.type !== 'step',
        symbol: 'circle',
        symbolSize: 5,
        showSymbol: false,
        itemStyle: { color },
        lineStyle: { width: 2, color },
        areaStyle:
          s.area
            ? {
                color: {
                  type: 'linear',
                  x: 0,
                  y: 0,
                  x2: 0,
                  y2: 1,
                  colorStops: [
                    { offset: 0, color: color + '40' },
                    { offset: 1, color: color + '05' },
                  ],
                },
              }
            : undefined,
        yAxisIndex: s.yAxisIndex || 0,
        data: s.data,
      };
    });

    // y 轴配置（支持双轴）
    const yAxisList: any = Array.isArray(yAxisName)
      ? [
          {
            type: 'value',
            name: yAxisName[0],
            min: yAxisMin,
            max: yAxisMax,
            splitLine: { lineStyle: { type: 'dashed' } },
            axisLabel: {
              formatter: (v: any) => `${v}${Array.isArray(yAxisName) ? '' : valueSuffix}`,
            },
          },
          {
            type: 'value',
            name: yAxisName[1],
            splitLine: { show: false },
            axisLabel: { formatter: (v: any) => `${v}${valueSuffix}` },
          },
        ]
      : {
          type: 'value',
          name: yAxisName,
          min: yAxisMin,
          max: yAxisMax,
          splitLine: { lineStyle: { type: 'dashed' } },
          axisLabel: {
            formatter: (v: any) =>
              Math.abs(v) >= 10000
                ? `${(v / 10000).toFixed(1)}w${valueSuffix}`
                : `${v}${valueSuffix}`,
          },
        };

    return {
      color: palette,
      title: title
        ? {
            text: title,
            left: 0,
            top: 0,
            textStyle: { fontSize: 14, fontWeight: 500, color: '#1f1f1f' },
          }
        : undefined,
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(0,0,0,0.8)',
        borderColor: 'transparent',
        textStyle: { color: '#fff', fontSize: 12 },
        axisPointer: { type: 'cross' },
        valueFormatter: (v: any) =>
          typeof v === 'number' ? `${v.toLocaleString('zh-CN')}${valueSuffix}` : v,
      },
      grid: {
        left: 60,
        right: Array.isArray(yAxisName) ? 60 : 24,
        top: title ? 40 : 16,
        bottom: xAxisName ? 40 : 30,
        containLabel: true,
      },
      legend: showLegend
        ? {
            data: series.map((s) => s.name),
            top: title ? 0 : 0,
            right: 0,
            icon: 'roundRect',
            itemWidth: 12,
            itemHeight: 3,
          }
        : undefined,
      xAxis: {
        type: categories ? 'category' : 'category',
        data: categories,
        boundaryGap: series.some((s) => s.type === 'bar'),
        name: xAxisName,
        nameLocation: 'end',
        nameTextStyle: { color: '#8c8c8c', fontSize: 12 },
        axisLabel: {
          color: '#8c8c8c',
          hideOverlap: true,
        },
        axisLine: { lineStyle: { color: '#e5e5e5' } },
      },
      yAxis: yAxisList,
      series: seriesConfig,
      ...extraOption,
    } as EChartsOption;
  }, [
    series,
    categories,
    palette,
    title,
    xAxisName,
    yAxisName,
    showLegend,
    yAxisMin,
    yAxisMax,
    valueSuffix,
    extraOption,
  ]);

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

export default LineChart;
