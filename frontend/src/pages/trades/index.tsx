import { Card, Typography } from 'antd';

const { Title, Paragraph } = Typography;

// 交易记录页面
const TradesPage = () => {
  return (
    <Card>
      <Title level={3}>交易记录</Title>
      <Paragraph type="secondary">查看历史交易记录（占位内容）。</Paragraph>
    </Card>
  );
};

export default TradesPage;
