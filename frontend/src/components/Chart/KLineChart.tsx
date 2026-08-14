import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Spin, Empty } from 'antd';
import type { EChartsOption } from 'echarts';
import type { KlinePoint } from '@/types';

export interface KLineChartProps {
  /** K 线数据 */
  data: KlinePoint[];
  /** loading */
  loading?: boolean;
  /** 图表高度 */
  height?: number | string;
  /** 主标题 */
  title?: string;
  /** 空数据提示 */
  emptyText?: string;
  /** 样式 */
  style?: React.CSSProperties;
}

const KLineChart = ({
  data,
  loading,
  height = 400,
  title,
  emptyText = '暂无K线数据',
  style,
}: KLineChartProps) => {
  const isEmpty = !loading && (!data || data.length === 0);

  const option: EChartsOption = useMemo(() => {
    if (!data || data.length === 0) return {};

    // 时间类目
    const categories = data.map((k) => {
      const d = new Date(k.timestamp);
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      const hh = String(d.getHours()).padStart(2, '0');
      const mi = String(d.getMinutes()).padStart(2, '0');
      // 按时间跨度决定显示格式
      const range = data.length > 1 ? data[data.length - 1].timestamp - data[0].timestamp : 0;
      if (range <= 86400000) return `${mm}-${dd} ${hh}:${mi}`; // 1天内
      if (range <= 604800000) return `${mm}-${dd} ${hh}:${mi}`; // 1周内
      return `${mm}-${dd}`; // 更长时间
    });

    // 蜡烛图 OHLC 数据
    const ohlc = data.map((k) => [k.open, k.close, k.low, k.high]);

    // 成交量数据
    const volumes = data.map((k) => k.volume);

    // 计算价格范围，留出成交量空间
    const prices = data.flatMap((k) => [k.high, k.low]);
    const maxPrice = Math.max(...prices);
    const minPrice = Math.min(...prices);

    // 判断涨跌颜色
    const upColor = '#ef5350'; // 红涨（中国习惯）
    const downColor = '#26a69a'; // 绿跌

    // 计算 MA 线
    const calcMA = (days: number) => {
      return data.map((_, i) => {
        if (i < days - 1) return '-';
        let sum = 0;
        for (let j = 0; j < days; j++) {
          sum += data[i - j].close;
        }
        return +(sum / days).toFixed(2);
      });
    };

    const ma5 = calcMA(5);
    const ma10 = calcMA(10);
    const ma20 = calcMA(20);

    return {
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
        axisPointer: {
          type: 'cross',
        },
        backgroundColor: 'rgba(0,0,0,0.85)',
        borderColor: 'transparent',
        textStyle: { color: '#fff', fontSize: 12 },
        formatter: (params: any) => {
          const dataIndex = params[0]?.dataIndex;
          if (dataIndex == null) return '';
          const k = data[dataIndex];
          const cat = params[0]?.axisValue || '';
          const change = k.close >= k.open
            ? `<span style="color:${upColor}">+${((k.close - k.open) / k.open * 100).toFixed(2)}%</span>`
            : `<span style="color:${downColor}">${((k.close - k.open) / k.open * 100).toFixed(2)}%</span>`;
          return `
            <div style="font-size:13px;font-weight:600;margin-bottom:4px">${cat}</div>
            <div>开: ${k.open.toLocaleString()}  |  收: ${k.close.toLocaleString()}  |  ${change}</div>
            <div>高: ${k.high.toLocaleString()}  |  低: ${k.low.toLocaleString()}</div>
            <div>成交量: ${k.volume.toLocaleString()}</div>
          `;
        },
      },
      grid: [
        { left: 56, right: 16, top: title ? 40 : 16, bottom: 80, height: 'auto' },
        { left: 56, right: 16, top: 'auto', bottom: 16, height: 50 },
      ],
      xAxis: [
        {
          type: 'category',
          data: categories,
          axisLine: { lineStyle: { color: '#e5e5e5' } },
          axisLabel: {
            color: '#8c8c8c',
            fontSize: 11,
            hideOverlap: true,
          },
          splitLine: { show: false },
          gridIndex: 0,
        },
        {
          type: 'category',
          data: categories,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
          gridIndex: 1,
        },
      ],
      yAxis: [
        {
          type: 'value',
          scale: true,
          splitLine: { lineStyle: { type: 'dashed', color: '#e8e8e8' } },
          axisLabel: {
            color: '#8c8c8c',
            fontSize: 11,
            formatter: (v: number) => v.toLocaleString(),
          },
          gridIndex: 0,
          min: (value: any) => Math.floor(value.min * 0.995),
          max: (value: any) => Math.ceil(value.max * 1.005),
        },
        {
          type: 'value',
          scale: true,
          splitLine: { show: false },
          axisLabel: { show: true, color: '#8c8c8c', fontSize: 10 },
          gridIndex: 1,
          min: 0,
        },
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 80,
          end: 100,
        },
        {
          type: 'slider',
          xAxisIndex: [0, 1],
          start: 80,
          end: 100,
          height: 14,
          bottom: 0,
          borderColor: '#e5e5e5',
          fillerColor: 'rgba(22, 119, 255, 0.15)',
          handleStyle: { borderColor: '#1677ff', color: '#1677ff' },
          textStyle: { fontSize: 10, color: '#8c8c8c' },
        },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: ohlc,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            color: upColor,
            color0: downColor,
            borderColor: upColor,
            borderColor0: downColor,
          },
          markPoint: {
            data: [
              { type: 'max', name: '最高价' },
              { type: 'min', name: '最低价' },
            ],
            symbol: 'pin',
            symbolSize: 40,
            label: {
              formatter: (p: any) => p.value?.toLocaleString(),
              fontSize: 10,
            },
          },
        },
        {
          name: 'MA5',
          type: 'line',
          data: ma5,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 1.5, color: '#ff9800' },
          xAxisIndex: 0,
          yAxisIndex: 0,
        },
        {
          name: 'MA10',
          type: 'line',
          data: ma10,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 1.5, color: '#2196f3' },
          xAxisIndex: 0,
          yAxisIndex: 0,
        },
        {
          name: 'MA20',
          type: 'line',
          data: ma20,
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 1.5, color: '#9c27b0' },
          xAxisIndex: 0,
          yAxisIndex: 0,
        },
        {
          name: '成交量',
          type: 'bar',
          data: volumes.map((v, i) => ({
            value: v,
            itemStyle: {
              color: data[i].close >= data[i].open ? upColor : downColor,
            },
          })),
          xAxisIndex: 1,
          yAxisIndex: 1,
          barWidth: '60%',
        },
      ],
      axisPointer: {
        link: [
          { xAxisIndex: [0, 1] },
        ],
      },
    } as EChartsOption;
  }, [data, title]);

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

export default KLineChart;