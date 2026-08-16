import React, { useEffect, useRef, useMemo } from 'react';
import * as echarts from 'echarts';
import { Card } from 'antd';
import type { KeyLevel, LatestTradeEvent, ClosedTradeEvent } from '@/types/ai-backtest';

interface Props {
  klineWindow: Array<{
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    time: string;
  }>;
  keyLevels?: KeyLevel[];
  trades?: Array<{
    event: 'open' | 'close';
    data: LatestTradeEvent | ClosedTradeEvent;
    klineIndex?: number;
  }>;
  currentIndex?: number;
  height?: number;
}

// 中国习惯：红涨绿跌
const UP_COLOR = '#ef5350';
const DOWN_COLOR = '#26a69a';
const SUPPORT_COLOR = '#13c2c2'; // 青色支撑
const RESISTANCE_COLOR = '#eb2f96'; // 品红阻力
const CURRENT_HIGHLIGHT = 'rgba(22, 119, 255, 0.15)';

const AIBacktestKlineChart: React.FC<Props> = ({
  klineWindow,
  keyLevels,
  trades,
  currentIndex,
  height = 420,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  // 时间类目
  const categories = useMemo(() => {
    return klineWindow.map((k) => {
      const d = new Date(k.time);
      if (isNaN(d.getTime())) return k.time;
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      const hh = String(d.getHours()).padStart(2, '0');
      const mi = String(d.getMinutes()).padStart(2, '0');
      return `${mm}-${dd} ${hh}:${mi}`;
    });
  }, [klineWindow]);

  // 初始化 / 销毁
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;

    // 容器尺寸变化时自适应
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  // 数据 / 配置更新
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (!klineWindow || klineWindow.length === 0) {
      chart.clear();
      return;
    }

    // 蜡烛图 OHLC: [open, close, low, high]
    const ohlc = klineWindow.map((k) => [k.open, k.close, k.low, k.high]);

    // 成交量（涨跌配色）
    const volumes = klineWindow.map((k) => ({
      value: k.volume,
      itemStyle: { color: k.close >= k.open ? UP_COLOR : DOWN_COLOR },
    }));

    // 关键位 markLine：支撑=青色虚线，阻力=品红虚线
    const keyLevelMarkLine: any =
      keyLevels && keyLevels.length > 0
        ? {
            symbol: 'none',
            silent: true,
            data: keyLevels.map((level) => ({
              yAxis: level.price,
              lineStyle: {
                type: 'dashed',
                color: level.type === 'support' ? SUPPORT_COLOR : RESISTANCE_COLOR,
                width: 1,
              },
              label: {
                formatter: `${level.type === 'support' ? '支撑' : '阻力'} ${level.price}`,
                position: 'insideEndTop',
                fontSize: 10,
                color: level.type === 'support' ? SUPPORT_COLOR : RESISTANCE_COLOR,
              },
            })),
          }
        : undefined;

    // 交易事件 markPoint：开多=红色箭头向上，开空=绿色箭头向下，平仓=圆点+盈亏标签
    const tradeMarkPoint: any =
      trades && trades.length > 0
        ? {
            data: trades.map((t) => {
              const idx = t.klineIndex ?? 0;
              if (t.event === 'open') {
                const d = t.data as LatestTradeEvent;
                const isLong = d.direction === 'long';
                return {
                  coord: [idx, d.entry_price],
                  symbol: 'arrow',
                  symbolSize: 14,
                  symbolRotate: isLong ? 0 : 180,
                  itemStyle: { color: isLong ? UP_COLOR : DOWN_COLOR },
                  label: {
                    show: true,
                    formatter: isLong ? '开多' : '开空',
                    position: isLong ? 'bottom' : 'top',
                    fontSize: 10,
                    color: isLong ? UP_COLOR : DOWN_COLOR,
                  },
                };
              }
              const d = t.data as ClosedTradeEvent;
              const profit = d.pnl >= 0;
              return {
                coord: [idx, d.exit_price],
                symbol: 'circle',
                symbolSize: 12,
                itemStyle: { color: profit ? UP_COLOR : DOWN_COLOR },
                label: {
                  show: true,
                  formatter: `${profit ? '+' : ''}${d.pnl.toFixed(2)}`,
                  position: 'top',
                  fontSize: 10,
                  color: profit ? UP_COLOR : DOWN_COLOR,
                },
              };
            }),
          }
        : undefined;

    // 当前 K 线高亮 markArea
    const currentMarkArea: any =
      currentIndex != null && currentIndex >= 0 && currentIndex < klineWindow.length
        ? {
            silent: true,
            itemStyle: { color: CURRENT_HIGHLIGHT, borderColor: 'transparent' },
            data: [
              [
                { xAxis: currentIndex - 0.5 },
                { xAxis: currentIndex + 0.5 },
              ],
            ],
          }
        : undefined;

    // dataZoom：跟随当前 K 线
    const total = klineWindow.length;
    const showCount = 80;
    let startPct = 0;
    let endPct = 100;
    if (total > showCount) {
      const focusIdx = currentIndex != null ? currentIndex : total - 1;
      const startIdx = Math.max(0, focusIdx - showCount + 10);
      const endIdx = Math.min(total, focusIdx + 10);
      startPct = (startIdx / total) * 100;
      endPct = (endIdx / total) * 100;
    }

    const option: echarts.EChartsOption = {
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: 'rgba(0,0,0,0.85)',
        borderColor: 'transparent',
        textStyle: { color: '#fff', fontSize: 12 },
        formatter: (params: any) => {
          const dataIndex = params[0]?.dataIndex;
          if (dataIndex == null) return '';
          const k = klineWindow[dataIndex];
          if (!k) return '';
          const cat = params[0]?.axisValue || '';
          const changePct = k.open !== 0 ? ((k.close - k.open) / k.open) * 100 : 0;
          const changeStr =
            changePct >= 0 ? `+${changePct.toFixed(2)}%` : `${changePct.toFixed(2)}%`;
          const changeColor = changePct >= 0 ? UP_COLOR : DOWN_COLOR;
          return `
            <div style="font-size:13px;font-weight:600;margin-bottom:4px">${cat}</div>
            <div>开: ${k.open}  收: ${k.close}  <span style="color:${changeColor}">${changeStr}</span></div>
            <div>高: ${k.high}  低: ${k.low}</div>
            <div>成交量: ${k.volume.toLocaleString()}</div>
          `;
        },
      },
      grid: [
        { left: 56, right: 16, top: 16, bottom: 84 },
        { left: 56, right: 16, top: 'auto', bottom: 28, height: 48 },
      ],
      xAxis: [
        {
          type: 'category',
          data: categories,
          gridIndex: 0,
          boundaryGap: true,
          axisLine: { lineStyle: { color: '#e5e5e5' } },
          axisLabel: { color: '#8c8c8c', fontSize: 11, hideOverlap: true },
          splitLine: { show: false },
        },
        {
          type: 'category',
          data: categories,
          gridIndex: 1,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          type: 'value',
          scale: true,
          gridIndex: 0,
          splitLine: { lineStyle: { type: 'dashed', color: '#e8e8e8' } },
          axisLabel: { color: '#8c8c8c', fontSize: 11 },
        },
        {
          type: 'value',
          scale: true,
          gridIndex: 1,
          splitLine: { show: false },
          axisLabel: { show: false },
        },
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: startPct,
          end: endPct,
        },
        {
          type: 'slider',
          xAxisIndex: [0, 1],
          start: startPct,
          end: endPct,
          height: 16,
          bottom: 4,
          borderColor: '#e5e5e5',
          fillerColor: 'rgba(22, 119, 255, 0.15)',
          handleStyle: { borderColor: '#1677ff', color: '#1677ff' },
          textStyle: { fontSize: 10, color: '#8c8c8c' },
        },
      ],
      axisPointer: {
        link: [{ xAxisIndex: [0, 1] }],
      },
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: ohlc,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            color: UP_COLOR,
            color0: DOWN_COLOR,
            borderColor: UP_COLOR,
            borderColor0: DOWN_COLOR,
          },
          markLine: keyLevelMarkLine,
          markPoint: tradeMarkPoint,
          markArea: currentMarkArea,
        },
        {
          name: '成交量',
          type: 'bar',
          data: volumes,
          xAxisIndex: 1,
          yAxisIndex: 1,
          barWidth: '60%',
        },
      ],
    };

    chart.setOption(option, true);
  }, [klineWindow, keyLevels, trades, currentIndex, categories]);

  return (
    <Card size="small" title="K线图" style={{ marginBottom: 16 }}>
      <div style={{ position: 'relative', width: '100%', height }}>
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
        {(!klineWindow || klineWindow.length === 0) && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#8c8c8c',
              pointerEvents: 'none',
            }}
          >
            暂无K线数据
          </div>
        )}
      </div>
    </Card>
  );
};

export default AIBacktestKlineChart;
