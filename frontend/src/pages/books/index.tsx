import { Card, Typography } from 'antd';

const { Title, Paragraph } = Typography;

// 书籍学习页面
const BooksPage = () => {
  return (
    <Card>
      <Title level={3}>书籍学习</Title>
      <Paragraph type="secondary">交易相关书籍阅读与学习笔记（占位内容）。</Paragraph>
    </Card>
  );
};

export default BooksPage;
