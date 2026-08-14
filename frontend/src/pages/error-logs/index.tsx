import ErrorLogPanel from '@/pages/system/ErrorLogPanel';
import { PageContainer } from '@/components/Common';

const ErrorLogsPage = () => {
  return (
    <PageContainer
      breadcrumbs={[{ title: '错误日志' }]}
      title="错误日志"
      description="系统错误日志的查看、检索和管理"
      card={false}
      padding={0}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 8,
          padding: 24,
          minHeight: 200,
        }}
      >
        <ErrorLogPanel />
      </div>
    </PageContainer>
  );
};

export default ErrorLogsPage;