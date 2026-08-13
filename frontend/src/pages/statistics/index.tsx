import { Card, Typography } from 'antd';

const { Title, Paragraph } = Typography;

// 统计分析页面
const StatisticsPage = () => {
  return (
    <Card>
      <Title level={3}>统计分析</Title>
      <Paragraph type="secondary">交易数据统计与可视化分析（占位内容）。</Paragraph>
    </Card>
  );
};

export default StatisticsPage;
