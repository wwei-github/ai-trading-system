import { Card, Typography } from 'antd';

const { Title, Paragraph } = Typography;

// 系统设置页面
const SystemPage = () => {
  return (
    <Card>
      <Title level={3}>系统设置</Title>
      <Paragraph type="secondary">系统参数与偏好设置（占位内容）。</Paragraph>
    </Card>
  );
};

export default SystemPage;
