import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Spin } from 'antd';
import type { EChartsOption } from 'echarts';
import { EmptyState } from '@/components/Common';

export interface BarChartData {
  name: string;
  value: number;
  category?: string;
}

export interface BarChartProps {
  data: BarChartData[];
  title?: string;
  loading?: boolean;
  horizontal?: boolean;
  stacked?: boolean;
  xName?: string;
  yName?: string;
  height?: number | string;
  colors?: string[];
  formatter?: (params: any) => string;
  showLegend?: boolean;
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

const BarChart = ({
  data,
  title,
  loading,
  horizontal = false,
  stacked = false,
  xName,
  yName,
  height = 320,
  colors,
  formatter,
  showLegend = true,
  style,
}: BarChartProps) => {
  const palette = colors || DEFAULT_COLORS;
  const isEmpty = !loading && data.length === 0;

  const option: EChartsOption = useMemo(() => {
    const categories = [...new Set(data.map((d) => d.name))];
    const categorySet = [...new Set(data.map((d) => d.category).filter(Boolean))];
    const hasCategory = categorySet.length > 0;

    let series: any[] = [];

    if (hasCategory) {
      series = categorySet.map((cat, idx) => {
        const color = palette[idx % palette.length];
        const values = categories.map((name) => {
          const item = data.find((d) => d.name === name && d.category === cat);
          return item ? item.value : 0;
        });
        return {
          name: cat,
          type: 'bar',
          stack: stacked ? 'total' : undefined,
          barMaxWidth: 40,
          itemStyle: { color, borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
          emphasis: { focus: 'series' },
          data: values,
        };
      });
    } else {
      const values = data.map((d) => d.value);
      series = [
        {
          name: title || '数值',
          type: 'bar',
          barMaxWidth: 40,
          itemStyle: {
            color: palette[0],
            borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
          },
          emphasis: { focus: 'series' },
          data: values,
        },
      ];
    }

    const xAxisBase = {
      name: horizontal ? xName : undefined,
      nameLocation: 'end' as const,
      nameTextStyle: { color: '#8c8c8c', fontSize: 12 },
      axisLabel: { color: '#8c8c8c', hideOverlap: true },
      axisLine: { lineStyle: { color: '#e5e5e5' } },
      splitLine: { lineStyle: { type: 'dashed' as const } },
    };

    const yAxisBase = {
      name: horizontal ? undefined : yName,
      nameLocation: 'end' as const,
      nameTextStyle: { color: '#8c8c8c', fontSize: 12 },
      axisLabel: { color: '#8c8c8c' },
      axisLine: { lineStyle: { color: '#e5e5e5' } },
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
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(0,0,0,0.8)',
        borderColor: 'transparent',
        textStyle: { color: '#fff', fontSize: 12 },
        formatter: formatter,
      },
      grid: {
        left: 60,
        right: 24,
        top: title ? 40 : 16,
        bottom: (horizontal ? yName : xName) ? 40 : 30,
        containLabel: true,
      },
      legend: showLegend && hasCategory
        ? {
            data: categorySet,
            top: title ? 0 : 0,
            right: 0,
            icon: 'roundRect',
            itemWidth: 12,
            itemHeight: 8,
          }
        : undefined,
      xAxis: horizontal
        ? { type: 'value', ...xAxisBase }
        : { type: 'category', data: categories, ...xAxisBase, splitLine: undefined },
      yAxis: horizontal
        ? { type: 'category', data: categories, ...yAxisBase, splitLine: undefined }
        : { type: 'value', ...yAxisBase },
      series,
    } as EChartsOption;
  }, [data, palette, title, horizontal, stacked, xName, yName, formatter, showLegend]);

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
      <EmptyState
        height={typeof height === 'number' ? height : 320}
        style={style}
      />
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

export default BarChart;
