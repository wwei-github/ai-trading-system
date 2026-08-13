import { Card, Typography } from 'antd';

const { Title, Paragraph } = Typography;

// 币种分析页面
const CoinsPage = () => {
  return (
    <Card>
      <Title level={3}>币种分析</Title>
      <Paragraph type="secondary">币种行情与趋势分析（占位内容）。</Paragraph>
    </Card>
  );
};

export default CoinsPage;
