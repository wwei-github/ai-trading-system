import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  Col,
  Descriptions,
  Row,
  Segmented,
  Space,
  Tag,
  Typography,
  Avatar,
  Grid,
} from 'antd';
import {
  DashboardOutlined,
  BankOutlined,
  SwapOutlined,
  ThunderboltOutlined,
  RobotOutlined,
  WalletOutlined,
  RiseOutlined,
  FallOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import {
  StatisticCard,
  PageContainer,
  AmountText,
} from '@/components/Common';
import { LineChart, PieChart } from '@/components/Chart';
import { statisticsApi, accountApi } from '@/api';
import type { ProfitTrendParams, AssetDistributionItem } from '@/types';

const { useBreakpoint } = Grid;
const { Text, Paragraph } = Typography;

type TrendRange = NonNullable<ProfitTrendParams['range']>;

const RANGE_OPTIONS = [
  { label: '近 7 日', value: '7d' as TrendRange },
  { label: '近 30 日', value: '30d' as TrendRange },
  { label: '近 90 日', value: '90d' as TrendRange },
];

const DashboardPage = () => {
  const navigate = useNavigate();
  const screens = useBreakpoint();
  const [trendRange, setTrendRange] = useState<TrendRange>('30d');

  // ========== 查询：概览 + 趋势 + 分布 + 账号列表 ==========
  const overviewQ = useQuery({
    queryKey: ['statistics', 'overview'],
    queryFn: () => statisticsApi.getOverview(),
  });

  const trendQ = useQuery({
    queryKey: ['statistics', 'profit-trend', trendRange],
    queryFn: () => statisticsApi.getProfitTrend({ range: trendRange }),
  });

  const distributionQ = useQuery({
    queryKey: ['statistics', 'asset-distribution'],
    queryFn: () => statisticsApi.getAssetDistribution(),
  });

  const accountsQ = useQuery({
    queryKey: ['accounts', 'overview-list'],
    queryFn: () => accountApi.getList({ page: 1, page_size: 50 }),
  });

  const overview = overviewQ.data;

  // ========== 资产趋势图表数据 ==========
  const lineChartProps = useMemo(() => {
    const data = trendQ.data || [];
    const categories = data.map((p) => p.date.slice(5)); // MM-DD
    return {
      categories,
      series: [
        {
          name: '资产净值',
          data: data.map((p) => p.total_asset),
          color: '#1677ff',
          area: true,
        },
      ],
      loading: trendQ.isLoading,
      valueSuffix: ' USDT',
      height: 340,
      yAxisName: '净值',
      xAxisName: trendRange === '7d' ? '日期（近7日）' : '日期',
    };
  }, [trendQ.data, trendQ.isLoading, trendRange]);

  // ========== 资产分布饼图 ==========
  const pieChartData: AssetDistributionItem[] = useMemo(
    () => distributionQ.data || [],
    [distributionQ.data],
  );

  // ========== 快捷入口配置 ==========
  const quickEntries = [
    {
      key: 'trades',
      title: '录入交易',
      desc: '手动录入交易记录',
      icon: <SwapOutlined />,
      color: '#1677ff',
      onClick: () => navigate('/trades'),
    },
    {
      key: 'accounts',
      title: '新增账号',
      desc: '绑定交易所 API Key',
      icon: <BankOutlined />,
      color: '#52c41a',
      onClick: () => navigate('/accounts'),
    },
    {
      key: 'strategies',
      title: '新建策略',
      desc: '策略规则与回测',
      icon: <ThunderboltOutlined />,
      color: '#722ed1',
      onClick: () => navigate('/strategies'),
    },
    {
      key: 'ai',
      title: 'AI 助手',
      desc: '对话分析与信号生成',
      icon: <RobotOutlined />,
      color: '#fa8c16',
      onClick: () => navigate('/ai'),
    },
  ];

  return (
    <PageContainer
      padding={0}
      breadcrumbs={[]}
      card={false}
      description={undefined}
      subHeader={undefined}
    >
      {/* ========== 顶部：4 个指标卡片 ========== */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <StatisticCard
            title="总资产"
            value={overview?.total_asset ?? 0}
            loading={overviewQ.isLoading}
            suffix=" USDT"
            icon={<WalletOutlined />}
            iconBgColor="#1677ff"
            tooltip="所有已绑定交易所账号的合计资产"
            delta={overview?.today_profit}
            deltaText="今日盈亏"
            precision={2}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatisticCard
            title="可用余额"
            value={overview?.available_balance ?? 0}
            loading={overviewQ.isLoading}
            suffix=" USDT"
            icon={<DashboardOutlined />}
            iconBgColor="#52c41a"
            delta={undefined}
            footer={
              <Text type="secondary" style={{ fontSize: 12 }}>
                冻结：
                <AmountText
                  value={overview?.frozen_balance ?? 0}
                  precision={2}
                  suffix=" USDT"
                />
              </Text>
            }
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatisticCard
            title="累计盈亏"
            value={overview?.total_profit ?? 0}
            loading={overviewQ.isLoading}
            suffix=" USDT"
            colored
            icon={
              (overview?.total_profit ?? 0) >= 0 ? (
                <RiseOutlined />
              ) : (
                <FallOutlined />
              )
            }
            iconBgColor={(overview?.total_profit ?? 0) >= 0 ? '#52c41a' : '#ff4d4f'}
            delta={overview ? overview.win_rate * 100 : 0}
            deltaText={`胜率 ${(overview?.win_rate ?? 0).toFixed(2)}%`}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatisticCard
            title="今日交易"
            value={overview?.today_trade_count ?? 0}
            loading={overviewQ.isLoading}
            suffix=" 笔"
            precision={0}
            icon={<SwapOutlined />}
            iconBgColor="#fa8c16"
            footer={
              <Space size={16} style={{ fontSize: 12 }}>
                <Text type="secondary">
                  成交金额：
                  <AmountText
                    value={overview?.today_trade_amount ?? 0}
                    suffix=" USDT"
                    fontWeight={500}
                    precision={2}
                  />
                </Text>
                <Text type="secondary">
                  活跃币种：<b style={{ color: '#1f1f1f' }}>{overview?.active_coin_count}</b>
                </Text>
              </Space>
            }
          />
        </Col>
      </Row>

      {/* ========== 中部：今日简报（左） + 资产趋势（右） ========== */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={10}>
          <Card
            title={
              <Space>
                <span style={{ fontSize: 16, fontWeight: 500 }}>📊 今日简报</span>
                <Tag color="blue">{new Date().toLocaleDateString('zh-CN')}</Tag>
              </Space>
            }
            styles={{ body: { padding: 20 } }}
            style={{ height: '100%' }}
          >
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="今日盈亏">
                <AmountText
                  value={overview?.today_profit ?? 0}
                  colored
                  showSign
                  suffix=" USDT"
                  fontWeight={600}
                  fontSize={15}
                />
              </Descriptions.Item>
              <Descriptions.Item label="今日交易笔数">
                <b>{overview?.today_trade_count ?? 0}</b> 笔
              </Descriptions.Item>
              <Descriptions.Item label="今日成交金额">
                <AmountText
                  value={overview?.today_trade_amount ?? 0}
                  suffix=" USDT"
                  fontWeight={600}
                />
              </Descriptions.Item>
              <Descriptions.Item label="活跃币种数">
                <b>{overview?.active_coin_count ?? 0}</b> 个
              </Descriptions.Item>
              <Descriptions.Item label="历史胜率">
                {overview ? `${(overview.win_rate * 100).toFixed(2)}%` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="已绑定账号">
                <b>{accountsQ.data?.total ?? 0}</b> 个
              </Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 20 }}>
              <Paragraph type="secondary" style={{ marginBottom: 8, fontSize: 13 }}>
                💡 快捷入口
              </Paragraph>
              <Space wrap>
                {['/trades', '/accounts', '/statistics'].map((p) => (
                  <Tag
                    key={p}
                    color="blue"
                    style={{ cursor: 'pointer', padding: '4px 12px', fontSize: 13 }}
                    onClick={() => navigate(p)}
                  >
                    {p === '/trades'
                      ? '→ 交易记录'
                      : p === '/accounts'
                      ? '→ 账号管理'
                      : '→ 统计分析'}
                  </Tag>
                ))}
              </Space>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card
            title={
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span style={{ fontSize: 16, fontWeight: 500 }}>📈 资产净值趋势</span>
                <Segmented
                  size="small"
                  value={trendRange}
                  options={RANGE_OPTIONS}
                  onChange={(v) => setTrendRange(v as TrendRange)}
                />
              </div>
            }
            styles={{ body: { padding: '12px 4px 0' } }}
            style={{ height: '100%' }}
          >
            <LineChart {...lineChartProps} />
          </Card>
        </Col>
      </Row>

      {/* ========== 中部二：资产分布（左） + 快捷入口（右） ========== */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card
            title={<span style={{ fontSize: 16, fontWeight: 500 }}>💰 币种资产分布</span>}
            style={{ height: '100%' }}
            styles={{ body: { paddingTop: 4 } }}
          >
            <PieChart
              height={screens.lg ? 320 : 280}
              loading={distributionQ.isLoading}
              data={pieChartData}
              valueSuffix=" USDT"
              donut
              centerText={{
                top: `${((accountsQ.data?.items || []).length > 0 ? '' : '')}`,
                bottom: '',
              }}
            />
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card
            title={<span style={{ fontSize: 16, fontWeight: 500 }}>⚡ 快捷入口</span>}
            style={{ height: '100%' }}
          >
            <Row gutter={[16, 16]}>
              {quickEntries.map((entry) => (
                <Col xs={12} md={12} xl={6} key={entry.key}>
                  <Card
                    hoverable
                    onClick={entry.onClick}
                    styles={{ body: { padding: 20 } }}
                    style={{
                      borderRadius: 12,
                      border: '1px solid #f0f0f0',
                      transition: 'all 0.2s',
                    }}
                  >
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 12,
                        background: `${entry.color}15`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 22,
                        color: entry.color,
                        marginBottom: 14,
                      }}
                    >
                      {entry.icon}
                    </div>
                    <div
                      style={{
                        fontSize: 15,
                        fontWeight: 600,
                        color: '#1f1f1f',
                        marginBottom: 4,
                      }}
                    >
                      {entry.title}
                    </div>
                    <div style={{ fontSize: 12, color: '#8c8c8c', lineHeight: 1.6 }}>
                      {entry.desc}
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>

            {/* 小贴士 */}
            <div
              style={{
                marginTop: 20,
                padding: 16,
                background: '#f6ffed',
                border: '1px solid #b7eb8f',
                borderRadius: 10,
              }}
            >
              <Space size={10} align="start">
                <Avatar size={36} style={{ background: '#52c41a' }}>
                  <PlusOutlined />
                </Avatar>
                <div style={{ flex: 1 }}>
                  <Text strong style={{ color: '#389e0d', fontSize: 14 }}>
                    还没有数据？先录入您的第一笔交易吧！
                  </Text>
                  <Paragraph type="secondary" style={{ margin: '6px 0 0', fontSize: 12 }}>
                    从「录入交易」开始积累数据，统计分析与策略回测模块将基于这些数据产出有价值的洞察。
                  </Paragraph>
                </div>
              </Space>
            </div>
          </Card>
        </Col>
      </Row>
    </PageContainer>
  );
};

export default DashboardPage;
