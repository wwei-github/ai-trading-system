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
import type { PieChartData } from '@/components/Chart';
import { statisticsApi, accountApi } from '@/api';
import { EXCHANGE_OPTIONS } from '@/types';

const { useBreakpoint } = Grid;
const { Text, Paragraph } = Typography;

const DAYS_OPTIONS = [
  { label: '近 7 日', value: 7 },
  { label: '近 30 日', value: 30 },
  { label: '近 90 日', value: 90 },
];

const DashboardPage = () => {
  const navigate = useNavigate();
  const screens = useBreakpoint();
  const [trendDays, setTrendDays] = useState<number>(30);

  // ========== 查询：汇总 + 资产趋势 + 盈亏趋势 + 交易所分布 + 币种排名 + 账号列表 ==========
  const summaryQ = useQuery({
    queryKey: ['statistics', 'summary'],
    queryFn: () => statisticsApi.getSummary(),
  });

  const assetTrendQ = useQuery({
    queryKey: ['statistics', 'asset-trend', trendDays],
    queryFn: () => statisticsApi.getAssetTrend({ days: trendDays }),
  });

  const pnlQ = useQuery({
    queryKey: ['statistics', 'pnl', 'daily'],
    queryFn: () => statisticsApi.getPnl({ period: 'daily' }),
  });

  const exchangeDistQ = useQuery({
    queryKey: ['statistics', 'exchange-distribution'],
    queryFn: () => statisticsApi.getExchangeDistribution(),
  });

  const coinRankingQ = useQuery({
    queryKey: ['statistics', 'coin-ranking'],
    queryFn: () => statisticsApi.getCoinRanking(),
  });

  const accountsQ = useQuery({
    queryKey: ['accounts', 'overview-list'],
    queryFn: () => accountApi.getList(),
  });

  const overview = summaryQ.data;
  const accounts = accountsQ.data || [];
  const winRatePct = (overview?.win_rate ?? 0) * 100;

  // ========== 资产净值趋势图表数据 ==========
  const assetLineProps = useMemo(() => {
    const data = assetTrendQ.data || [];
    const categories = data.map((p) => p.date.slice(5, 10)); // MM-DD
    return {
      categories,
      series: [
        {
          name: '资产净值',
          data: data.map((p) => Number(p.total_usd)),
          color: '#1677ff',
          area: true,
        },
      ],
      loading: assetTrendQ.isLoading,
      valueSuffix: ' USD',
      height: 340,
      yAxisName: '净值 (USD)',
      xAxisName: `日期（近 ${trendDays} 日）`,
    };
  }, [assetTrendQ.data, assetTrendQ.isLoading, trendDays]);

  // ========== 盈亏趋势图表数据（双轴：盈亏 + 交易笔数） ==========
  const pnlLineProps = useMemo(() => {
    const data = pnlQ.data || [];
    const categories = data.map((p) => p.period.slice(5, 10)); // MM-DD
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
      height: 300,
      yAxisName: ['盈亏 (USDT)', '笔数'] as [string, string],
      valueSuffix: '',
    };
  }, [pnlQ.data, pnlQ.isLoading]);

  // ========== 交易所分布饼图数据 ==========
  const pieData: PieChartData[] = useMemo(() => {
    const dist = exchangeDistQ.data || {};
    return Object.entries(dist).map(([key, value]) => {
      const opt = EXCHANGE_OPTIONS.find((o) => o.value === key);
      return { name: opt?.label ?? key, value: Number(value) };
    });
  }, [exchangeDistQ.data]);

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
            title="成交总额"
            value={Number(overview?.total_volume ?? 0)}
            loading={summaryQ.isLoading}
            suffix=" USDT"
            icon={<WalletOutlined />}
            iconBgColor="#1677ff"
            tooltip="所有交易的总成交额"
            precision={2}
            footer={
              <Text type="secondary" style={{ fontSize: 12 }}>
                总手续费：
                <AmountText
                  value={overview?.total_fee ?? 0}
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
            iconBgColor={(overview?.profit_loss ?? 0) >= 0 ? '#52c41a' : '#ff4d4f'}
            deltaText={`历史胜率 ${winRatePct.toFixed(2)}%`}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
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
        <Col xs={24} sm={12} lg={6}>
          <StatisticCard
            title="历史胜率"
            value={winRatePct}
            loading={summaryQ.isLoading}
            suffix=" %"
            precision={2}
            icon={<DashboardOutlined />}
            iconBgColor="#722ed1"
            footer={
              <Space size={16} style={{ fontSize: 12 }}>
                <Text type="secondary">
                  活跃币种：
                  <b style={{ color: '#1f1f1f' }}>{coinRankingQ.data?.length ?? 0}</b>
                </Text>
                <Text type="secondary">
                  已绑定账号：<b style={{ color: '#1f1f1f' }}>{accounts.length}</b>
                </Text>
              </Space>
            }
          />
        </Col>
      </Row>

      {/* ========== 中部：交易概览（左） + 资产净值趋势（右） ========== */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={10}>
          <Card
            title={
              <Space>
                <span style={{ fontSize: 16, fontWeight: 500 }}>📊 交易概览</span>
                <Tag color="blue">{new Date().toLocaleDateString('zh-CN')}</Tag>
              </Space>
            }
            styles={{ body: { padding: 20 } }}
            style={{ height: '100%' }}
          >
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="累计盈亏">
                <AmountText
                  value={overview?.profit_loss ?? 0}
                  colored
                  showSign
                  suffix=" USDT"
                  fontWeight={600}
                  fontSize={15}
                />
              </Descriptions.Item>
              <Descriptions.Item label="总交易笔数">
                <b>{overview?.total_trades ?? 0}</b> 笔
              </Descriptions.Item>
              <Descriptions.Item label="总成交额">
                <AmountText
                  value={overview?.total_volume ?? 0}
                  suffix=" USDT"
                  fontWeight={600}
                />
              </Descriptions.Item>
              <Descriptions.Item label="总手续费">
                <AmountText
                  value={overview?.total_fee ?? 0}
                  suffix=" USDT"
                  fontWeight={600}
                />
              </Descriptions.Item>
              <Descriptions.Item label="历史胜率">
                {overview ? `${winRatePct.toFixed(2)}%` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="已绑定账号">
                <b>{accounts.length}</b> 个
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
                  value={trendDays}
                  options={DAYS_OPTIONS}
                  onChange={(v) => setTrendDays(Number(v))}
                />
              </div>
            }
            styles={{ body: { padding: '12px 4px 0' } }}
            style={{ height: '100%' }}
          >
            <LineChart {...assetLineProps} />
          </Card>
        </Col>
      </Row>

      {/* ========== 盈亏趋势 ========== */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24}>
          <Card
            title={<span style={{ fontSize: 16, fontWeight: 500 }}>💹 盈亏趋势（按日）</span>}
            styles={{ body: { padding: '12px 4px 0' } }}
          >
            <LineChart {...pnlLineProps} />
          </Card>
        </Col>
      </Row>

      {/* ========== 中部二：交易所分布（左） + 快捷入口（右） ========== */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card
            title={<span style={{ fontSize: 16, fontWeight: 500 }}>💰 交易所分布</span>}
            style={{ height: '100%' }}
            styles={{ body: { paddingTop: 4 } }}
          >
            <PieChart
              height={screens.lg ? 320 : 280}
              loading={exchangeDistQ.isLoading}
              data={pieData}
              donut
              centerText={{
                top: `${pieData.length}`,
                bottom: '交易所',
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
