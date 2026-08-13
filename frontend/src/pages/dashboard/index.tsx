import { Card, Typography } from 'antd';

const { Title, Paragraph } = Typography;

// 工作台页面
const DashboardPage = () => {
  return (
    <Card>
      <Title level={3}>工作台</Title>
      <Paragraph type="secondary">欢迎使用 AI 智能交易管理系统，此处为工作台概览页面（占位内容）。</Paragraph>
    </Card>
  );
};

export default DashboardPage;
