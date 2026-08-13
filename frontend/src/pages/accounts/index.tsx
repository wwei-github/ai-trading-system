import { Card, Typography } from 'antd';

const { Title, Paragraph } = Typography;

// 交易所账号页面
const AccountsPage = () => {
  return (
    <Card>
      <Title level={3}>交易所账号</Title>
      <Paragraph type="secondary">管理各交易所账号信息（占位内容）。</Paragraph>
    </Card>
  );
};

export default AccountsPage;
