import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Col,
  Row,
  Space,
  Button,
  DatePicker,
  Select,
  Table,
  Tag,
  message,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  RiseOutlined,
  FallOutlined,
  SwapOutlined,
  WalletOutlined,
  DashboardOutlined,
  ShoppingOutlined,
  ExportOutlined,
  BankOutlined,
  FundOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import {
  StatisticCard,
  PageContainer,
  AmountText,
  EmptyState,
} from '@/components/Common';
import { LineChart, PieChart, BarChart } from '@/components/Chart';
import type { PieChartData, BarChartData } from '@/components/Chart';
import { statisticsApi, accountApi } from '@/api';
import { EXCHANGE_OPTIONS } from '@/types';
import type {
  OverviewData,
  ProfitTrendPoint,
  CoinRankingItem,
  StatsQueryParams,
} from '@/types';

const { RangePicker } = DatePicker;
const { Title, Text } = Typography;

interface FilterState {
  dateRange: [Dayjs, Dayjs] | null;
  account_id: string | undefined;
}

const StatisticsPage = () => {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<FilterState>({
    dateRange: [dayjs().subtract(30, 'day'), dayjs()],
    account_id: undefined,
  });

  const queryParams: StatsQueryParams = useMemo(() => {
    const params: StatsQueryParams = {};
    if (filters.dateRange && filters.dateRange[0] && filters.dateRange[1]) {
      params.start_date = filters.dateRange[0].format('YYYY-MM-DD');
      params.end_date = filters.dateRange[1].format('YYYY-MM-DD');
    }
    if (filters.account_id) {
      params.account_id = filters.account_id;
    }
    return params;
  }, [filters]);

  const summaryQ = useQuery({
    queryKey: ['statistics', 'summary', queryParams],
    queryFn: () => statisticsApi.getSummary(queryParams),
  });

  const pnlQ = useQuery({
    queryKey: ['statistics', 'pnl', queryParams],
    queryFn: () =>
      statisticsApi.getPnl({
        period: 'daily',
        start_date: queryParams.start_date,
        end_date: queryParams.end_date,
      }),
  });

  const coinRankingQ = useQuery({
    queryKey: ['statistics', 'coin-ranking', queryParams],
    queryFn: () => statisticsApi.getCoinRanking(queryParams),
  });

  const exchangeDistQ = useQuery({
    queryKey: ['statistics', 'exchange-distribution', queryParams],
    queryFn: () => statisticsApi.getExchangeDistribution(queryParams),
  });

  const sideDistQ = useQuery({
    queryKey: ['statistics', 'side-distribution', queryParams],
    queryFn: () => statisticsApi.getSideDistribution(queryParams),
  });

  const accountsQ = useQuery({
    queryKey: ['accounts', 'overview-list'],
    queryFn: () => accountApi.getList(),
  });

  const overview = summaryQ.data;
  const winRatePct = (overview?.win_rate ?? 0) * 100;

  const exportMutation = useMutation({
    mutationFn: () => statisticsApi.exportReport(queryParams),
    onMutate: () => {
      message.loading('正在导出报表...', 0);
    },
    onSuccess: (blob) => {
      message.destroy();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const timestamp = dayjs().format('YYYYMMDD_HHmmss');
      a.download = `交易统计报表_${timestamp}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      message.success('报表导出成功');
    },
    onError: () => {
      message.destroy();
      message.error('报表导出失败');
    },
  });

  const handleSearch = (values: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, ...values }));
  };

  const handleReset = () => {
    setFilters({
      dateRange: [dayjs().subtract(30, 'day'), dayjs()],
      account_id: undefined,
    });
  };

  const handleExport = () => {
    exportMutation.mutate();
  };

  const pnlLineProps = useMemo(() => {
    const data: ProfitTrendPoint[] = pnlQ.data || [];
    const categories = data.map((p) =>
      (p.date || p.period).slice(5, 10),
    );
    return {
      categories,
      series: [
        {
          name: '盈亏',
          data: data.map((p) => Number(p.pnl)),
          color: '#1677ff',
          area: true,
        },
        {
          name: '交易笔数',
          data: data.map((p) => p.trade_count),
          color: '#fa8c16',
          yAxisIndex: 1,
        },
      ],
      loading: pnlQ.isLoading,
      height: 320,
      yAxisName: ['盈亏 (USDT)', '笔数'] as [string, string],
      valueSuffix: '',
    };
  }, [pnlQ.data, pnlQ.isLoading]);

  const exchangePieData: PieChartData[] = useMemo(() => {
    const dist = exchangeDistQ.data || {};
    return Object.entries(dist).map(([key, value]) => {
      const opt = EXCHANGE_OPTIONS.find((o) => o.value === key);
      return { name: opt?.label ?? key, value: Number(value) };
    });
  }, [exchangeDistQ.data]);

  const coinBarData: BarChartData[] = useMemo(() => {
    const data = coinRankingQ.data || [];
    return data
      .slice(0, 10)
      .map((item) => ({
        name: item.symbol,
        value: Number(item.net_pnl ?? 0),
      }))
      .sort((a, b) => b.value - a.value);
  }, [coinRankingQ.data]);

  const sideBarData: BarChartData[] = useMemo(() => {
    const dist = sideDistQ.data || {};
    return Object.entries(dist).map(([key, value]) => ({
      name: key === 'buy' ? '买入' : key === 'sell' ? '卖出' : key,
      value: Number(value),
    }));
  }, [sideDistQ.data]);

  const columns: ColumnsType<CoinRankingItem> = [
    {
      title: '排名',
      key: 'rank',
      width: 70,
      align: 'center',
      render: (_text, _record, index) => {
        const rank = index + 1;
        if (rank === 1) return <Tag color="gold">🥇 1</Tag>;
        if (rank === 2) return <Tag color="silver">🥈 2</Tag>;
        if (rank === 3) return <Tag color="bronze">🥉 3</Tag>;
        return <Text type="secondary">{rank}</Text>;
      },
    },
    {
      title: '币种',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 120,
      render: (symbol: string) => (
        <Tag color="blue" style={{ fontSize: 13, padding: '2px 10px' }}>
          {symbol}
        </Tag>
      ),
    },
    {
      title: '交易笔数',
      dataIndex: 'trade_count',
      key: 'trade_count',
      width: 120,
      align: 'right',
      sorter: (a, b) => a.trade_count - b.trade_count,
      render: (val: number) => <b>{val}</b>,
    },
    {
      title: '总成交额',
      dataIndex: 'total_volume',
      key: 'total_volume',
      width: 160,
      align: 'right',
      sorter: (a, b) => a.total_volume - b.total_volume,
      render: (val: number) => (
        <AmountText value={val} precision={2} suffix=" USDT" />
      ),
    },
    {
      title: '净盈亏',
      dataIndex: 'net_pnl',
      key: 'net_pnl',
      width: 160,
      align: 'right',
      sorter: (a, b) => Number(a.net_pnl ?? 0) - Number(b.net_pnl ?? 0),
      render: (val: number) => (
        <AmountText
          value={val ?? 0}
          colored
          showSign
          precision={2}
          suffix=" USDT"
          fontWeight={600}
        />
      ),
    },
    {
      title: '胜率',
      dataIndex: 'win_rate',
      key: 'win_rate',
      width: 120,
      align: 'right',
      sorter: (a, b) => Number(a.win_rate ?? 0) - Number(b.win_rate ?? 0),
      render: (val: number) => {
        const pct = (val ?? 0) * 100;
        const color = pct >= 50 ? '#52c41a' : pct >= 30 ? '#fa8c16' : '#ff4d4f';
        return <Text style={{ color, fontWeight: 600 }}>{pct.toFixed(2)}%</Text>;
      },
    },
    {
      title: '手续费',
      dataIndex: 'total_fee',
      key: 'total_fee',
      width: 140,
      align: 'right',
      sorter: (a, b) => a.total_fee - b.total_fee,
      render: (val: number) => (
        <AmountText value={val} precision={2} suffix=" USDT" />
      ),
    },
  ];

  const accountOptions = useMemo(() => {
    const accounts = accountsQ.data || [];
    return accounts.map((acc) => ({
      value: acc.id,
      label: (
        <Space>
          <BankOutlined />
          <span>{acc.name}</span>
          <Tag color="blue" style={{ marginLeft: 8 }}>
            {EXCHANGE_OPTIONS.find((o) => o.value === acc.exchange)?.label ??
              acc.exchange}
          </Tag>
        </Space>
      ),
    }));
  }, [accountsQ.data]);

  return (
    <PageContainer
      breadcrumbs={[{ title: '统计分析' }]}
      padding={0}
      card={false}
      description={undefined}
      subHeader={undefined}
    >
      <Card style={{ marginBottom: 16 }} styles={{ body: { paddingBottom: 0 } }}>
        <Row gutter={16} style={{ alignItems: 'flex-end' }}>
          <Col xs={24} sm={12} md={8} style={{ marginBottom: 12 }}>
            <div style={{ marginBottom: 4, fontSize: 13, color: '#8c8c8c' }}>
              时间范围
            </div>
            <RangePicker
              style={{ width: '100%' }}
              value={filters.dateRange}
              onChange={(dates) =>
                handleSearch({
                  dateRange: dates as [Dayjs, Dayjs] | null,
                })
              }
            />
          </Col>
          <Col xs={24} sm={12} md={6} style={{ marginBottom: 12 }}>
            <div style={{ marginBottom: 4, fontSize: 13, color: '#8c8c8c' }}>
              交易账号
            </div>
            <Select
              style={{ width: '100%' }}
              allowClear
              placeholder="全部账号"
              value={filters.account_id}
              loading={accountsQ.isLoading}
              options={accountOptions}
              onChange={(value) => handleSearch({ account_id: value })}
            />
          </Col>
          <Col xs={24} sm={24} md={10} style={{ marginBottom: 12 }}>
            <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
              <Button onClick={handleReset}>重置</Button>
              <Button
                type="primary"
                icon={<ExportOutlined />}
                loading={exportMutation.isPending}
                onClick={handleExport}
              >
                导出报表
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatisticCard
            title="累计盈亏"
            value={Number(overview?.profit_loss ?? 0)}
            loading={summaryQ.isLoading}
            suffix=" USDT"
            colored
            showSign
            icon={
              (overview?.profit_loss ?? 0) >= 0 ? (
                <RiseOutlined />
              ) : (
                <FallOutlined />
              )
            }
            iconBgColor={
              (overview?.profit_loss ?? 0) >= 0 ? '#52c41a' : '#ff4d4f'
            }
            precision={2}
          />
        </Col>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatisticCard
            title="成交总额"
            value={Number(overview?.total_volume ?? 0)}
            loading={summaryQ.isLoading}
            suffix=" USDT"
            icon={<WalletOutlined />}
            iconBgColor="#1677ff"
            precision={2}
          />
        </Col>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatisticCard
            title="交易笔数"
            value={overview?.total_trades ?? 0}
            loading={summaryQ.isLoading}
            suffix=" 笔"
            precision={0}
            icon={<SwapOutlined />}
            iconBgColor="#fa8c16"
            footer={
              <Space size={16} style={{ fontSize: 12 }}>
                <Text type="secondary">
                  买入：<b style={{ color: '#1f1f1f' }}>{overview?.buy_count ?? 0}</b>
                </Text>
                <Text type="secondary">
                  卖出：<b style={{ color: '#1f1f1f' }}>{overview?.sell_count ?? 0}</b>
                </Text>
              </Space>
            }
          />
        </Col>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatisticCard
            title="历史胜率"
            value={winRatePct}
            loading={summaryQ.isLoading}
            suffix=" %"
            precision={2}
            icon={<DashboardOutlined />}
            iconBgColor="#722ed1"
          />
        </Col>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatisticCard
            title="总手续费"
            value={Number(overview?.total_fee ?? 0)}
            loading={summaryQ.isLoading}
            suffix=" USDT"
            icon={<BarChartOutlined />}
            iconBgColor="#13c2c2"
            precision={2}
          />
        </Col>
        <Col xs={24} sm={12} lg={8} xl={4}>
          <StatisticCard
            title="买卖次数"
            value={(overview?.buy_count ?? 0) + (overview?.sell_count ?? 0)}
            loading={summaryQ.isLoading}
            suffix=" 次"
            precision={0}
            icon={<ShoppingOutlined />}
            iconBgColor="#eb2f96"
            footer={
              <Space size={16} style={{ fontSize: 12 }}>
                <Text type="secondary">
                  买入占比：
                  <b style={{ color: '#1677ff' }}>
                    {overview && overview.buy_count + overview.sell_count > 0
                      ? (
                          (overview.buy_count /
                            (overview.buy_count + overview.sell_count)) *
                          100
                        ).toFixed(1)
                      : 0}
                    %
                  </b>
                </Text>
              </Space>
            }
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}>
          <Card
            title={
              <Space>
                <FundOutlined style={{ color: '#1677ff' }} />
                <span style={{ fontSize: 16, fontWeight: 500 }}>盈亏趋势</span>
              </Space>
            }
            styles={{ body: { padding: '12px 4px 0' } }}
          >
            <LineChart {...pnlLineProps} />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card
            title={
              <Space>
                <BankOutlined style={{ color: '#722ed1' }} />
                <span style={{ fontSize: 16, fontWeight: 500 }}>交易所分布</span>
              </Space>
            }
            styles={{ body: { paddingTop: 4 } }}
          >
            <PieChart
              height={320}
              loading={exchangeDistQ.isLoading}
              data={exchangePieData}
              donut
              centerText={{
                top: `${exchangePieData.length}`,
                bottom: '交易所',
              }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <BarChartOutlined style={{ color: '#fa8c16' }} />
                <span style={{ fontSize: 16, fontWeight: 500 }}>币种盈亏排行 TOP10</span>
              </Space>
            }
            styles={{ body: { padding: '12px 4px 0' } }}
          >
            <BarChart
              height={340}
              loading={coinRankingQ.isLoading}
              data={coinBarData}
              xName="币种"
              yName="净盈亏 (USDT)"
              colors={['#1677ff']}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <SwapOutlined style={{ color: '#52c41a' }} />
                <span style={{ fontSize: 16, fontWeight: 500 }}>买卖方向分布</span>
              </Space>
            }
            styles={{ body: { padding: '12px 4px 0' } }}
          >
            <BarChart
              height={340}
              loading={sideDistQ.isLoading}
              data={sideBarData}
              horizontal
              xName="次数"
              yName="方向"
              colors={['#52c41a', '#ff4d4f']}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title={
          <Space>
            <DashboardOutlined style={{ color: '#722ed1' }} />
            <span style={{ fontSize: 16, fontWeight: 500 }}>币种统计明细</span>
            <Tag color="blue">{coinRankingQ.data?.length ?? 0} 个币种</Tag>
          </Space>
        }
        extra={
          <Button
            icon={<ExportOutlined />}
            loading={exportMutation.isPending}
            onClick={handleExport}
          >
            导出报表
          </Button>
        }
      >
        <Table<CoinRankingItem>
          rowKey="symbol"
          columns={columns}
          dataSource={coinRankingQ.data || []}
          loading={coinRankingQ.isLoading}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条记录`,
          }}
          scroll={{ x: 900 }}
          locale={{
            emptyText: (
              <EmptyState
                height={200}
                description="暂无币种统计数据"
              />
            ),
          }}
        />
      </Card>
    </PageContainer>
  );
};

export default StatisticsPage;
