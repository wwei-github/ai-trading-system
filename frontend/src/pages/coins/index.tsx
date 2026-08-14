import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  Col,
  Row,
  Input,
  Segmented,
  Checkbox,
  Button,
  List,
  Tag,
  Space,
  Statistic,
  Switch,
  message,
  Pagination,
  Tooltip,
  Typography,
} from 'antd';
import {
  StarOutlined,
  StarFilled,
  SearchOutlined,
  ReloadOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  PageContainer,
  EmptyState,
  AmountText,
} from '@/components/Common';
import { LineChart } from '@/components/Chart';
import { coinApi } from '@/api/coins';
import type {
  Coin,
  CoinTicker,
  KlinePoint,
  KlinePeriod,
  CompareResultItem,
} from '@/types';

const { Title } = Typography;

const KLINE_PERIODS: KlinePeriod[] = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'];
const PAGE_SIZE = 20;
const COMPARE_DAYS = 30;

const CoinsPage = () => {
  const [searchKeyword, setSearchKeyword] = useState('');
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');
  const [favoriteSet, setFavoriteSet] = useState<Set<string>>(new Set());
  const [compareSet, setCompareSet] = useState<Set<string>>(new Set());
  const [period, setPeriod] = useState<KlinePeriod>('1d');

  const {
    data: coinList = [],
    isLoading: listLoading,
    refetch: refetchList,
  } = useQuery({
    queryKey: ['coins', 'list', { keyword: searchKeyword, favorite: favoriteOnly }],
    queryFn: () =>
      coinApi.getList({
        keyword: searchKeyword || undefined,
        favorite: favoriteOnly ? true : undefined,
      }),
  });

  const pagedCoins = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return coinList.slice(start, start + PAGE_SIZE);
  }, [coinList, page]);

  const {
    data: ticker,
    isLoading: tickerLoading,
  } = useQuery({
    queryKey: ['coins', 'ticker', selectedSymbol],
    queryFn: () => coinApi.getTicker(selectedSymbol),
    enabled: !!selectedSymbol,
  });

  const {
    data: kline = [],
    isLoading: klineLoading,
  } = useQuery({
    queryKey: ['coins', 'kline', selectedSymbol, period],
    queryFn: () =>
      coinApi.getKline({
        symbol: selectedSymbol,
        period,
        limit: 200,
      }),
    enabled: !!selectedSymbol,
  });

  const compareSymbols = useMemo(() => Array.from(compareSet), [compareSet]);

  const {
    data: compareResult = [],
    isLoading: compareLoading,
  } = useQuery({
    queryKey: ['coins', 'compare', compareSymbols, period],
    queryFn: () =>
      coinApi.compare({
        symbols: compareSymbols,
        period,
        days: COMPARE_DAYS,
      }),
    enabled: compareSymbols.length > 0,
  });

  const klineChartData = useMemo(() => {
    if (!kline || kline.length === 0) {
      return { categories: [], series: [] };
    }
    const categories = kline.map((k) =>
      dayjs(k.timestamp).format(
        period === '1m' || period === '5m' || period === '15m'
          ? 'HH:mm'
          : period === '1h' || period === '4h'
            ? 'MM-DD HH:mm'
            : 'YYYY-MM-DD',
      ),
    );
    const closeData = kline.map((k) => k.close);
    return {
      categories,
      series: [
        {
          name: '收盘价',
          data: closeData,
          area: true,
          color: '#1677ff',
        },
      ],
    };
  }, [kline, period]);

  const compareChartData = useMemo(() => {
    if (!compareResult || compareResult.length === 0) {
      return { categories: [], series: [] };
    }
    const validItems = compareResult.filter((item) => item.symbol);
    if (validItems.length === 0) {
      return { categories: [], series: [] };
    }
    const series: any[] = [];
    let categories: string[] = [];
    validItems.forEach((item, idx) => {
      if (item.analysis && typeof item.analysis.indicators === 'object') {
        const indicators = item.analysis.indicators;
        const keys = Object.keys(indicators).sort();
        if (categories.length === 0) {
          categories = keys;
        }
        const values = keys.map((k) => {
          const v = indicators[k];
          return typeof v === 'number' ? v : 0;
        });
        const base = values[0] || 1;
        const normalized = values.map((v) => ((v - base) / Math.abs(base)) * 100);
        series.push({
          name: item.symbol,
          data: normalized,
          area: false,
        });
      } else {
        const mockLength = 20;
        if (categories.length === 0) {
          categories = Array.from({ length: mockLength }, (_, i) =>
            dayjs().subtract(mockLength - 1 - i, 'day').format('MM-DD'),
          );
        }
        const seed = (item.symbol?.length || 1) + idx;
        const values = Array.from({ length: mockLength }, (_, i) => {
          const base = 100 + (seed % 10);
          const trend = Math.sin((i + seed) / 3) * 10;
          return base + trend + (i % 5) * 0.5;
        });
        const first = values[0];
        const normalized = values.map((v) => ((v - first) / Math.abs(first)) * 100);
        series.push({
          name: item.symbol || `币种${idx + 1}`,
          data: normalized,
          area: false,
        });
      }
    });
    return { categories, series };
  }, [compareResult]);

  const selectedCoin = useMemo(() => {
    return coinList.find((c) => c.symbol === selectedSymbol);
  }, [coinList, selectedSymbol]);

  const displayTicker: CoinTicker | null = ticker || selectedCoin || null;

  const toggleFavorite = (symbol: string) => {
    setFavoriteSet((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) {
        next.delete(symbol);
        message.info(`已取消收藏 ${symbol}`);
      } else {
        next.add(symbol);
        message.success(`已收藏 ${symbol}`);
      }
      return next;
    });
  };

  const toggleCompare = (symbol: string, checked: boolean) => {
    setCompareSet((prev) => {
      const next = new Set(prev);
      if (checked) {
        if (next.size >= 6) {
          message.warning('最多支持同时对比 6 个币种');
          return prev;
        }
        next.add(symbol);
      } else {
        next.delete(symbol);
      }
      return next;
    });
  };

  const handleSelectCoin = (symbol: string) => {
    setSelectedSymbol(symbol);
  };

  const renderChangePercent = (value?: number) => {
    if (value === undefined || value === null) {
      return <Tag>-</Tag>;
    }
    const isPositive = value >= 0;
    return (
      <AmountText
        value={value}
        precision={2}
        colored
        showSign
        suffix="%"
        fontWeight={500}
      />
    );
  };

  return (
    <PageContainer
      breadcrumbs={[{ title: '币种分析' }]}
      title="币种分析"
      description="实时行情查看、K线走势分析与多币种横向对比"
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={() => refetchList()}
        >
          刷新
        </Button>
      }
    >
      <Row gutter={16}>
        <Col span={5} style={{ minWidth: 300 }}>
          <Card
            size="small"
            title={
              <Space>
                <BarChartOutlined />
                <span>币种列表</span>
              </Space>
            }
            styles={{ body: { padding: 12 } }}
          >
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Input
                allowClear
                prefix={<SearchOutlined />}
                placeholder="搜索币种名称/Symbol"
                value={searchKeyword}
                onChange={(e) => {
                  setSearchKeyword(e.target.value);
                  setPage(1);
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Space size={8}>
                  <Tag color="gold">
                    <StarFilled style={{ color: '#faad14' }} /> 仅收藏
                  </Tag>
                </Space>
                <Switch
                  size="small"
                  checked={favoriteOnly}
                  onChange={setFavoriteOnly}
                />
              </div>

              <div style={{ maxHeight: 'calc(100vh - 380px)', overflowY: 'auto', margin: '0 -12px' }}>
                <List
                  loading={listLoading}
                  dataSource={pagedCoins}
                  locale={{
                    emptyText: (
                      <EmptyState
                        description="暂无币种数据"
                        height={200}
                      />
                    ),
                  }}
                  renderItem={(coin: Coin) => {
                    const isSelected = coin.symbol === selectedSymbol;
                    const isFavorite = favoriteSet.has(coin.symbol);
                    const inCompare = compareSet.has(coin.symbol);
                    return (
                      <List.Item
                        key={coin.id}
                        onClick={() => handleSelectCoin(coin.symbol)}
                        style={{
                          cursor: 'pointer',
                          padding: '10px 12px',
                          background: isSelected ? '#e6f4ff' : 'transparent',
                          borderLeft: isSelected ? '3px solid #1677ff' : '3px solid transparent',
                          transition: 'all 0.15s',
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected) {
                            (e.currentTarget as HTMLDivElement).style.background = '#fafafa';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected) {
                            (e.currentTarget as HTMLDivElement).style.background = 'transparent';
                          }
                        }}
                      >
                        <div style={{ width: '100%' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                            <Space size={6}>
                              <Tooltip title={inCompare ? '从对比中移除' : '加入对比'}>
                                <Checkbox
                                  checked={inCompare}
                                  onClick={(e) => e.stopPropagation()}
                                  onChange={(e) => toggleCompare(coin.symbol, e.target.checked)}
                                />
                              </Tooltip>
                              <strong style={{ fontSize: 14 }}>{coin.symbol}</strong>
                              {coin.name && (
                                <span style={{ color: '#8c8c8c', fontSize: 12 }}>{coin.name}</span>
                              )}
                            </Space>
                            <Tooltip title={isFavorite ? '取消收藏' : '收藏'}>
                              <Button
                                type="text"
                                size="small"
                                icon={isFavorite ? <StarFilled style={{ color: '#faad14' }} /> : <StarOutlined />}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleFavorite(coin.symbol);
                                }}
                                style={{ padding: '0 4px' }}
                              />
                            </Tooltip>
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <AmountText
                              value={coin.current_price ?? 0}
                              precision={coin.current_price && coin.current_price < 1 ? 6 : 2}
                              prefix="$"
                              fontWeight={500}
                            />
                            {renderChangePercent(coin.price_change_24h)}
                          </div>
                        </div>
                      </List.Item>
                    );
                  }}
                />
              </div>

              {coinList.length > PAGE_SIZE && (
                <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 8, borderTop: '1px solid #f0f0f0' }}>
                  <Pagination
                    size="small"
                    current={page}
                    pageSize={PAGE_SIZE}
                    total={coinList.length}
                    showSizeChanger={false}
                    onChange={setPage}
                  />
                </div>
              )}
            </Space>
          </Card>
        </Col>

        <Col span={19}>
          <Space direction="vertical" style={{ width: '100%' }} size={16}>
            <Card
              size="small"
              loading={tickerLoading && !displayTicker}
              styles={{ body: { padding: 20 } }}
            >
              {displayTicker ? (
                <Row gutter={24} align="middle">
                  <Col flex="auto">
                    <Space align="center" size={16}>
                      <Title level={3} style={{ margin: 0 }}>
                        {displayTicker.symbol}
                        {displayTicker.name && (
                          <span style={{ color: '#8c8c8c', fontSize: 16, fontWeight: 400, marginLeft: 8 }}>
                            {displayTicker.name}
                          </span>
                        )}
                      </Title>
                      <Tooltip
                        title={favoriteSet.has(displayTicker.symbol) ? '取消收藏' : '收藏'}
                      >
                        <Button
                          type="text"
                          icon={
                            favoriteSet.has(displayTicker.symbol)
                              ? <StarFilled style={{ color: '#faad14', fontSize: 20 }} />
                              : <StarOutlined style={{ fontSize: 20 }} />
                          }
                          onClick={() => toggleFavorite(displayTicker.symbol)}
                        />
                      </Tooltip>
                    </Space>
                  </Col>
                  <Col>
                    <Statistic
                      title="当前价格"
                      value={displayTicker.current_price ?? 0}
                      prefix="$"
                      precision={displayTicker.current_price && displayTicker.current_price < 1 ? 6 : 2}
                      valueStyle={{ fontSize: 24, fontWeight: 600 }}
                    />
                  </Col>
                  <Col>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ color: '#8c8c8c', fontSize: 13, marginBottom: 4 }}>24h 涨跌</div>
                      <div style={{ fontSize: 20, fontWeight: 600 }}>
                        {renderChangePercent(displayTicker.price_change_24h)}
                      </div>
                    </div>
                  </Col>
                  <Col>
                    <Statistic
                      title="24h 成交量"
                      value={displayTicker.volume_24h ?? 0}
                      prefix="$"
                      precision={0}
                      valueStyle={{ fontSize: 18, fontWeight: 600 }}
                    />
                  </Col>
                </Row>
              ) : (
                <EmptyState
                  description="请在左侧选择一个币种开始分析"
                  height={140}
                />
              )}
            </Card>

            <Card
              size="small"
              title="K 线走势"
              extra={
                <Segmented
                  value={period}
                  onChange={(v) => setPeriod(v as KlinePeriod)}
                  options={KLINE_PERIODS.map((p) => ({ label: p, value: p }))}
                  size="small"
                  disabled={!selectedSymbol}
                />
              }
            >
              {selectedSymbol ? (
                <LineChart
                  categories={klineChartData.categories}
                  series={klineChartData.series}
                  loading={klineLoading}
                  height={380}
                  xAxisName="时间"
                  yAxisName="价格 (USDT)"
                  showLegend={false}
                  valueSuffix=" USDT"
                  emptyText="暂无K线数据"
                />
              ) : (
                <EmptyState
                  description="选择币种后查看 K 线走势"
                  height={380}
                />
              )}
            </Card>

            <Card
              size="small"
              title={
                <Space>
                  <span>多币种对比</span>
                  {compareSet.size > 0 && (
                    <Tag color="blue">已选 {compareSet.size} / 6</Tag>
                  )}
                </Space>
              }
              extra={
                compareSet.size > 0 ? (
                  <Space>
                    <Segmented
                      value={period}
                      onChange={(v) => setPeriod(v as KlinePeriod)}
                      options={['1h', '4h', '1d', '1w'].map((p) => ({ label: p, value: p }))}
                      size="small"
                    />
                    <Button
                      size="small"
                      onClick={() => setCompareSet(new Set())}
                    >
                      清空
                    </Button>
                  </Space>
                ) : null
              }
            >
              {compareSet.size > 0 ? (
                <>
                  <div style={{ marginBottom: 12, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {Array.from(compareSet).map((s) => (
                      <Tag
                        key={s}
                        closable
                        color="processing"
                        onClose={() => toggleCompare(s, false)}
                      >
                        {s}
                      </Tag>
                    ))}
                  </div>
                  <LineChart
                    categories={compareChartData.categories}
                    series={compareChartData.series}
                    loading={compareLoading}
                    height={320}
                    xAxisName="时间"
                    yAxisName="涨跌幅 (%)"
                    showLegend={true}
                    valueSuffix="%"
                    yAxisMin="dataMin"
                    yAxisMax="dataMax"
                    emptyText="暂无对比数据"
                  />
                </>
              ) : (
                <EmptyState
                  description="在左侧列表勾选 Checkbox 可添加币种进行对比（最多 6 个）"
                  height={280}
                />
              )}
            </Card>
          </Space>
        </Col>
      </Row>
    </PageContainer>
  );
};

export default CoinsPage;
