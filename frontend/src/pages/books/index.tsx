import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card, Col, Row, Segmented, Space, Tag, Typography, Input, Select, Button,
  Upload, Progress, Tree, List, Avatar, Skeleton, Form, message, Divider,
  Modal, Spin, Tabs, Descriptions, Alert, Table,
} from 'antd';
import type { UploadProps, TreeDataNode } from 'antd';
import {
  UploadOutlined, PlusOutlined, DeleteOutlined, LeftOutlined, RightOutlined,
  SendOutlined, ReloadOutlined, BookOutlined, BulbOutlined,
  QuestionCircleOutlined, LoadingOutlined,
} from '@ant-design/icons';
import { PageContainer, EmptyState, ConfirmButton, CrudModal } from '@/components/Common';
import { bookApi, strategyApi } from '@/api';
import type {
  Book, BookCreateData, ParseStatus, BookQAResponse, BookAnalyzeResult,
} from '@/types';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

type ReaderMode = 'reader' | 'knowledge' | 'qa';
type FontSize = 'small' | 'medium' | 'large';

interface QAMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: BookQAResponse['sources'];
}

const CATEGORY_OPTIONS = [
  { label: '全部类别', value: undefined },
  { label: '技术分析', value: '技术分析' },
  { label: '基础分析', value: '基础分析' },
  { label: '量化交易', value: '量化交易' },
  { label: '风险管理', value: '风险管理' },
  { label: '投资心理', value: '投资心理' },
  { label: '其他', value: '其他' },
];

const PARSE_STATUS_OPTIONS: Array<{ label: string; value: ParseStatus | undefined }> = [
  { label: '全部状态', value: undefined },
  { label: '待解析', value: 'pending' },
  { label: '解析中', value: 'parsing' },
  { label: '已完成', value: 'completed' },
  { label: '解析失败', value: 'failed' },
];

const PARSE_STATUS_TAG: Record<ParseStatus, { color: string; text: string }> = {
  pending: { color: 'default', text: '待解析' },
  parsing: { color: 'processing', text: '解析中' },
  completed: { color: 'success', text: '已完成' },
  failed: { color: 'error', text: '解析失败' },
};

const FONT_SIZE_OPTIONS: { label: string; value: FontSize }[] = [
  { label: '小', value: 'small' },
  { label: '中', value: 'medium' },
  { label: '大', value: 'large' },
];

const FONT_SIZE_MAP: Record<FontSize, { body: number; title: number; lineHeight: number }> = {
  small: { body: 13, title: 16, lineHeight: 1.7 },
  medium: { body: 15, title: 18, lineHeight: 1.8 },
  large: { body: 17, title: 20, lineHeight: 1.9 },
};

const generateId = () => Math.random().toString(36).slice(2, 10);

const BooksPage = () => {
  const queryClient = useQueryClient();

  const [keyword, setKeyword] = useState<string>('');
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [parseStatus, setParseStatus] = useState<ParseStatus | undefined>(undefined);

  const [selectedBook, setSelectedBook] = useState<Book | null>(null);
  const [readerMode, setReaderMode] = useState<ReaderMode>('reader');
  const [fontSize, setFontSize] = useState<FontSize>('medium');
  const [currentChapterOrder, setCurrentChapterOrder] = useState<number>(1);

  const [createModalOpen, setCreateModalOpen] = useState(false);

  const [qaInput, setQaInput] = useState('');
  const [qaMessages, setQaMessages] = useState<QAMessage[]>([]);

  // AI 分析相关状态
  const [analyzeModalOpen, setAnalyzeModalOpen] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<BookAnalyzeResult | null>(null);
  const [analyzeStrategyIds, setAnalyzeStrategyIds] = useState<string[]>([]);

  // 可选：获取所有策略用于 AI 分析时的参考选择
  const allStrategiesQ = useQuery({
    queryKey: ['strategies', 'list'],
    queryFn: () => strategyApi.getList(),
  });

  const booksQ = useQuery({
    queryKey: ['books', 'list', keyword, category, parseStatus],
    queryFn: () =>
      bookApi.getList({ keyword: keyword || undefined, category, parse_status: parseStatus }),
  });

  const bookDetailQ = useQuery({
    queryKey: ['books', 'detail', selectedBook?.id],
    queryFn: () => selectedBook!.id && bookApi.getDetail(selectedBook!.id),
    enabled: !!selectedBook,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.parse_status === 'parsing' ? 3000 : false;
    },
  });

  const notesQ = useQuery({
    queryKey: ['books', 'notes', selectedBook?.id],
    queryFn: () => selectedBook!.id && bookApi.getNotes(selectedBook!.id),
    enabled: !!selectedBook,
  });

  // 解析进度轮询
  const parseProgressQ = useQuery({
    queryKey: ['books', 'parse-progress', selectedBook?.id],
    queryFn: () => selectedBook!.id && bookApi.getParseProgress(selectedBook!.id),
    enabled: !!selectedBook && bookDetailQ.data?.parse_status === 'parsing',
    refetchInterval: 2000,
  });

  // 真实章节列表
  const chaptersQ = useQuery({
    queryKey: ['books', 'chapters', selectedBook?.id],
    queryFn: () => selectedBook!.id && bookApi.getChapters(selectedBook!.id),
    enabled: !!selectedBook && bookDetailQ.data?.parse_status === 'completed',
  });

  // 当前章节内容
  const chapterContentQ = useQuery({
    queryKey: ['books', 'chapter-content', selectedBook?.id, currentChapterOrder],
    queryFn: () =>
      selectedBook!.id && bookApi.getChapterContent(selectedBook!.id, currentChapterOrder),
    enabled: !!selectedBook && currentChapterOrder > 0 && bookDetailQ.data?.parse_status === 'completed',
  });

  // 关联策略
  const bookStrategiesQ = useQuery({
    queryKey: ['books', 'strategies', selectedBook?.id],
    queryFn: () => selectedBook!.id && bookApi.getStrategies(selectedBook!.id),
    enabled: !!selectedBook && bookDetailQ.data?.parse_status === 'completed',
  });

  const uploadMutation = useMutation({
    mutationFn: (formData: FormData) => bookApi.upload(formData),
    onSuccess: (book) => {
      message.success('书籍上传成功');
      queryClient.invalidateQueries({ queryKey: ['books', 'list'] });
      setSelectedBook(book);
      if (book?.id) {
        parseMutation.mutate(book.id);
      }
    },
    onError: () => message.error('书籍上传失败'),
  });

  const parseMutation = useMutation({
    mutationFn: (id: string) => bookApi.parseContent(id),
    onSuccess: (_data, id) => {
      message.success('解析任务已提交');
      queryClient.invalidateQueries({ queryKey: ['books', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['books', 'detail', id] });
      queryClient.invalidateQueries({ queryKey: ['books', 'parse-progress', id] });
    },
    onError: (err: any) => {
      const msg = err?.message || '';
      if (msg.includes('already parsing')) {
        message.info('书籍正在解析中，请稍候');
      } else {
        message.error('解析启动失败，请稍后重试');
      }
    },
  });

  const reparseMutation = useMutation({
    mutationFn: (id: string) => bookApi.reparseContent(id),
    onSuccess: (_data, id) => {
      message.success('重新解析任务已提交');
      queryClient.invalidateQueries({ queryKey: ['books', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['books', 'detail', id] });
      queryClient.invalidateQueries({ queryKey: ['books', 'parse-progress', id] });
    },
    onError: (err: any) => {
      message.error('重新解析启动失败: ' + (err?.message || '未知错误'));
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: BookCreateData) => bookApi.create(data),
    onSuccess: (data) => {
      message.success('书籍创建成功');
      setCreateModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ['books', 'list'] });
      setSelectedBook(data);
    },
    onError: () => message.error('书籍创建失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => bookApi.delete(id),
    onSuccess: () => {
      message.success('删除成功');
      setSelectedBook(null);
      queryClient.invalidateQueries({ queryKey: ['books', 'list'] });
    },
    onError: () => message.error('删除失败'),
  });

  const analyzeMutation = useMutation({
    mutationFn: (params: { bookId: string; saveStrategy: boolean; strategyName?: string; strategyIds?: string[] }) =>
      bookApi.analyze(params.bookId, {
        save_strategy: params.saveStrategy,
        strategy_name: params.strategyName,
        strategy_ids: params.strategyIds,
      }),
    onSuccess: (result) => {
      setAnalyzeResult(result);
      message.success('分析完成，交易系统已生成');
      queryClient.invalidateQueries({ queryKey: ['books', 'strategies'] });
    },
    onError: (err: any) => {
      message.error('分析失败: ' + (err?.message || '未知错误'));
    },
  });

  const qaMutation = useMutation({
    mutationFn: (params: { bookId: string; question: string }) =>
      bookApi.qa(params.bookId, params.question),
    onSuccess: (res, vars) => {
      const userMsg: QAMessage = { id: generateId(), role: 'user', content: vars.question };
      const assistantMsg: QAMessage = {
        id: generateId(), role: 'assistant', content: res.answer, sources: res.sources,
      };
      setQaMessages((prev) => [...prev, userMsg, assistantMsg]);
    },
    onError: () => message.error('问答失败'),
  });

  const books = booksQ.data || [];
  const detail = bookDetailQ.data || selectedBook;
  const notes = notesQ.data || [];
  const chapters = chaptersQ.data || [];
  const parseProgressData = parseProgressQ.data;
  const chapterContent = chapterContentQ.data?.content || '';
  const bookStrategies = bookStrategiesQ.data || [];

  const chapterTree: TreeDataNode[] = useMemo(() => {
    if (!chapters.length) return [];
    return chapters.map((ch) => ({
      key: String(ch.chapter_order),
      title: ch.title,
      isLeaf: true,
    }));
  }, [chapters]);

  const currentChapterIndex = chapters.findIndex((c) => c.chapter_order === currentChapterOrder);
  const currentChapter = chapters[currentChapterIndex];

  const fontSizeConf = FONT_SIZE_MAP[fontSize];

  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.pdf,.epub,.txt,.md,.docx',
    showUploadList: false,
    customRequest: async (options) => {
      const formData = new FormData();
      if (options.file) formData.append('file', options.file);
      try {
        await uploadMutation.mutateAsync(formData);
        options.onSuccess?.({}, new XMLHttpRequest());
      } catch (err) {
        options.onError?.(err as Error);
      }
    },
  };

  const handleSelectBook = (book: Book) => {
    setSelectedBook(book);
    setQaMessages([]);
    setCurrentChapterOrder(1);
    setReaderMode('reader');
  };

  const handlePrevChapter = () => {
    if (currentChapterOrder > 1) setCurrentChapterOrder(currentChapterOrder - 1);
  };

  const handleNextChapter = () => {
    if (currentChapterOrder < chapters.length) setCurrentChapterOrder(currentChapterOrder + 1);
  };

  const handleSendQA = async () => {
    if (!qaInput.trim() || !selectedBook) return;
    const question = qaInput.trim();
    setQaInput('');
    setQaMessages((prev) => [...prev, { id: generateId(), role: 'user', content: question }]);
    await qaMutation.mutateAsync({ bookId: selectedBook.id, question });
  };

  const handleAnalyze = () => {
    if (!selectedBook) return;
    setAnalyzeResult(null);
    setAnalyzeStrategyIds([]);
    setAnalyzeModalOpen(true);
  };

  const handleStartAnalyze = () => {
    if (!selectedBook) return;
    analyzeMutation.mutate({
      bookId: selectedBook.id,
      saveStrategy: true,
      strategyIds: analyzeStrategyIds.length > 0 ? analyzeStrategyIds : undefined,
    });
  };

  const renderCover = (book: Book) => {
    if (book.cover_url) {
      return (
        <div
          style={{
            height: 120,
            backgroundImage: `url(${book.cover_url})`,
            backgroundSize: 'cover', backgroundPosition: 'center',
            borderTopLeftRadius: 8, borderTopRightRadius: 8,
          }}
        />
      );
    }
    return (
      <div
        style={{
          height: 120,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderTopLeftRadius: 8, borderTopRightRadius: 8,
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 36,
        }}
      >
        <BookOutlined />
      </div>
    );
  };

  const parseStatusTag = (status?: ParseStatus) => {
    if (!status) return null;
    const conf = PARSE_STATUS_TAG[status];
    return <Tag color={conf.color}>{conf.text}</Tag>;
  };

  return (
    <PageContainer
      title="书籍学习"
      description="上传书籍，智能解析知识点，支持问答式学习"
      breadcrumbs={[{ title: '学习中心' }]}
      card={false}
      padding={0}
      extra={
        selectedBook ? (
          <ConfirmButton
            icon={<DeleteOutlined />}
            label="删除书籍"
            type="primary"
            danger
            title={`确认删除《${selectedBook.title}》？`}
            description="删除后书籍数据将无法恢复"
            onConfirm={async () => { await deleteMutation.mutateAsync(selectedBook.id); }}
            disabled={deleteMutation.isPending}
          />
        ) : null
      }
    >
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card
            styles={{ body: { padding: 16 } }}
            style={{ height: 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column' }}
          >
            <Space direction="vertical" size={12} style={{ marginBottom: 16 }}>
              <Row gutter={8}>
                <Col span={24}>
                  <Input
                    placeholder="搜索书名、作者..."
                    prefix={<span>🔍</span>}
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    allowClear
                  />
                </Col>
              </Row>
              <Row gutter={8}>
                <Col span={12}>
                  <Select
                    style={{ width: '100%' }} placeholder="类别"
                    value={category} onChange={setCategory}
                    options={CATEGORY_OPTIONS.filter((o) => o.value !== undefined).map((o) => ({ label: o.label, value: o.value }))}
                    allowClear
                  />
                </Col>
                <Col span={12}>
                  <Select
                    style={{ width: '100%' }} placeholder="解析状态"
                    value={parseStatus}
                    onChange={(v) => setParseStatus(v as ParseStatus | undefined)}
                    options={PARSE_STATUS_OPTIONS.filter((o) => o.value !== undefined).map((o) => ({ label: o.label, value: o.value }))}
                    allowClear
                  />
                </Col>
              </Row>
              <Space>
                <Upload {...uploadProps}>
                  <Button icon={<UploadOutlined />} type="primary" loading={uploadMutation.isPending}>
                    上传书籍
                  </Button>
                </Upload>
                <Button icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
                  新增书籍
                </Button>
              </Space>
            </Space>

            <Divider style={{ margin: '4px 0 12px' }} />

            <div style={{ flex: 1, overflowY: 'auto', paddingRight: 4 }}>
              {booksQ.isLoading ? (
                <List
                  dataSource={[1, 2, 3]}
                  renderItem={() => (
                    <List.Item style={{ padding: '8px 0', border: 'none' }}>
                      <Skeleton active paragraph={{ rows: 3 }} />
                    </List.Item>
                  )}
                />
              ) : books.length === 0 ? (
                <EmptyState description="暂无书籍，上传或新增第一本吧" height={260} />
              ) : (
                <Row gutter={[12, 12]}>
                  {books.map((book) => {
                    const isSelected = selectedBook?.id === book.id;
                    return (
                      <Col xs={12} xl={24} key={book.id}>
                        <Card
                          hoverable
                          styles={{ body: { padding: 0 } }}
                          onClick={() => handleSelectBook(book)}
                          style={{
                            border: isSelected ? '2px solid #1677ff' : '1px solid #f0f0f0',
                            borderRadius: 8, overflow: 'hidden', transition: 'all 0.2s',
                          }}
                        >
                          {renderCover(book)}
                          <div style={{ padding: 12 }}>
                            <Text
                              strong
                              style={{ display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden', fontSize: 14, marginBottom: 4 }}
                            >
                              {book.title}
                            </Text>
                            <div style={{ marginBottom: 8, minHeight: 18 }}>
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                {book.author || '未知作者'}
                              </Text>
                            </div>
                            <Space size={4} wrap style={{ marginBottom: 8 }}>
                              {book.category && <Tag color="blue" style={{ margin: 0 }}>{book.category}</Tag>}
                              {parseStatusTag(book.parse_status)}
                            </Space>
                            <Progress
                              percent={Math.round(book.progress * 100)}
                              size="small"
                              strokeColor="#1677ff"
                              style={{ margin: 0 }}
                            />
                          </div>
                        </Card>
                      </Col>
                    );
                  })}
                </Row>
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Card
            styles={{ body: { padding: 0 } }}
            style={{ height: 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column' }}
          >
            {!selectedBook ? (
              <EmptyState
                description="请从左侧选择一本书籍开始学习"
                height={400}
                image={<BookOutlined style={{ fontSize: 72, color: '#d9d9d9' }} />}
              />
            ) : (
              <>
                <div
                  style={{
                    padding: '12px 24px',
                    borderBottom: '1px solid #f0f0f0',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}
                >
                  <div>
                    <Space size={16}>
                      <div>
                        <Title level={5} style={{ margin: 0 }}>
                          {detail?.title || selectedBook.title}
                        </Title>
                        <Space size={8} style={{ marginTop: 2 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {detail?.author || selectedBook.author || '未知作者'}
                            {detail?.category ? ` · ${detail.category}` : ''}
                          </Text>
                          {detail?.parse_status === 'parsing' && (
                            <Tag icon={<LoadingOutlined />} color="processing">
                              解析中 {parseProgressData?.progress ? `${Math.round(parseProgressData.progress)}%` : ''}
                            </Tag>
                          )}
                          {detail?.parse_status === 'completed' && <Tag color="success">已解析</Tag>}
                          {detail?.parse_status === 'failed' && <Tag color="error">解析失败</Tag>}
                        </Space>
                      </div>
                      <Space>
                        {detail?.parse_status === 'completed' && (
                          <>
                            <Button type="primary" icon={<BulbOutlined />} onClick={handleAnalyze} loading={analyzeMutation.isPending}>
                              AI 分析生成策略
                            </Button>
                            <Button icon={<ReloadOutlined />} onClick={() => selectedBook && reparseMutation.mutate(selectedBook.id)} loading={reparseMutation.isPending} size="small">
                              重新解析
                            </Button>
                          </>
                        )}
                        {detail?.parse_status === 'failed' && (
                          <Button icon={<ReloadOutlined />} onClick={() => selectedBook && parseMutation.mutate(selectedBook.id)} loading={parseMutation.isPending} size="small">
                            重新解析
                          </Button>
                        )}
                      </Space>
                    </Space>

                    {/* 解析进度条 */}
                    {detail?.parse_status === 'parsing' && (
                      <div style={{ marginTop: 8 }}>
                        <Progress
                          percent={Math.round(parseProgressData?.progress ?? 0)}
                          size="small"
                          strokeColor={{ '0%': '#1677ff', '100%': '#52c41a' }}
                        />
                        <div style={{ marginTop: 4, fontSize: 12, color: '#8c8c8c' }}>
                          <Space size={12}>
                            <Text type="secondary">
                              {parseProgressData?.stage_description || '解析中...'}
                            </Text>
                            <Text type="secondary">
                              章节: {parseProgressData?.parsed_chapters ?? 0}/{parseProgressData?.total_chapters ?? '?'}
                            </Text>
                            <Text type="secondary">
                              知识块: {parseProgressData?.parsed_chunks ?? 0}
                            </Text>
                          </Space>
                        </div>
                      </div>
                    )}

                    {/* 解析失败提示 */}
                    {detail?.parse_status === 'failed' && (
                      <div style={{ marginTop: 8 }}>
                        <Alert
                          type="error"
                          message="解析失败"
                          description={detail?.parse_error_message || '请尝试重新解析'}
                          showIcon
                          action={
                            <Button size="small" onClick={() => selectedBook && parseMutation.mutate(selectedBook.id)}>
                              重新解析
                            </Button>
                          }
                        />
                      </div>
                    )}
                  </div>

                  <Segmented<ReaderMode>
                    value={readerMode}
                    onChange={setReaderMode}
                    options={[
                      { label: '📖 阅读', value: 'reader' },
                      { label: '💡 知识点', value: 'knowledge' },
                      { label: '❓ 问答', value: 'qa' },
                    ]}
                  />
                </div>

                {readerMode === 'reader' && (
                  <>
                    {detail?.parse_status !== 'completed' ? (
                      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <EmptyState
                          height={300}
                          description={detail?.parse_status === 'parsing' ? '正在解析中，请稍候...' : '请先解析书籍内容'}
                          image={<BookOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
                        />
                      </div>
                    ) : (
                      <>
                        <div
                          style={{
                            padding: '12px 24px', borderBottom: '1px solid #f0f0f0',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8,
                          }}
                        >
                          <Space>
                            <Button icon={<LeftOutlined />} onClick={handlePrevChapter} disabled={currentChapterIndex <= 0} size="small">
                              上一章
                            </Button>
                            <Text strong style={{ fontSize: fontSizeConf.title - 2 }}>
                              {currentChapter?.title || '加载中...'}
                            </Text>
                            <Button icon={<RightOutlined />} onClick={handleNextChapter} disabled={currentChapterIndex >= chapters.length - 1} size="small">
                              下一章
                            </Button>
                          </Space>
                          <Segmented<FontSize> size="small" value={fontSize} onChange={setFontSize} options={FONT_SIZE_OPTIONS} />
                        </div>

                        <Row style={{ flex: 1, overflow: 'hidden', margin: 0 }}>
                          <Col
                            xs={24} sm={8} md={6} lg={5} xl={4}
                            style={{ borderRight: '1px solid #f0f0f0', overflowY: 'auto', height: '100%', padding: '16px 8px' }}
                          >
                            <Text type="secondary" style={{ padding: '0 8px', fontSize: 12 }}>章节目录</Text>
                            {chaptersQ.isLoading ? (
                              <Skeleton active paragraph={{ rows: 5 }} style={{ padding: 8, marginTop: 8 }} />
                            ) : (
                              <Tree
                                treeData={chapterTree}
                                defaultExpandAll
                                selectedKeys={[String(currentChapterOrder)]}
                                onSelect={(keys) => { if (keys.length > 0) setCurrentChapterOrder(Number(keys[0])); }}
                                style={{ marginTop: 8, background: 'transparent' }}
                                showLine={{ showLeafIcon: false }}
                                blockNode
                              />
                            )}
                            {notes.length > 0 && (
                              <>
                                <Divider style={{ margin: '16px 0 8px' }} />
                                <Text type="secondary" style={{ padding: '0 8px', fontSize: 12 }}>我的笔记 ({notes.length})</Text>
                                <List
                                  size="small" dataSource={notes} style={{ marginTop: 8 }}
                                  renderItem={(note) => (
                                    <List.Item style={{ padding: '6px 8px' }}>
                                      <Text ellipsis={{ tooltip: note.content }} style={{ fontSize: 12 }}>📝 {note.content}</Text>
                                    </List.Item>
                                  )}
                                />
                              </>
                            )}
                          </Col>

                          <Col
                            xs={24} sm={16} md={18} lg={19} xl={20}
                            style={{ overflowY: 'auto', height: '100%', padding: '24px 40px', background: '#fefefe' }}
                          >
                            {chapterContentQ.isLoading ? (
                              <Skeleton active paragraph={{ rows: 12 }} />
                            ) : chapterContent ? (
                              <>
                                <Title level={4} style={{ marginBottom: 24, color: '#1f1f1f' }}>
                                  {currentChapter?.title}
                                </Title>
                                <div style={{ maxWidth: 800 }}>
                                  <Paragraph
                                    style={{
                                      fontSize: fontSizeConf.body, lineHeight: fontSizeConf.lineHeight,
                                      margin: 0, color: '#262626', whiteSpace: 'pre-wrap',
                                    }}
                                  >
                                    {chapterContent.split('\n').map((line, i) => (
                                      <span key={i}>
                                        {line}
                                        {i < chapterContent.split('\n').length - 1 && <br />}
                                      </span>
                                    ))}
                                  </Paragraph>
                                </div>
                              </>
                            ) : (
                              <EmptyState height={300} description="暂无章节内容" />
                            )}
                          </Col>
                        </Row>
                      </>
                    )}
                  </>
                )}

                {readerMode === 'knowledge' && (
                  <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
                    {detail?.parse_status !== 'completed' ? (
                      <EmptyState height={300} description="请先解析书籍内容" />
                    ) : (
                      <>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                          <Space>
                            <BulbOutlined style={{ color: '#faad14', fontSize: 20 }} />
                            <Text strong style={{ fontSize: 16 }}>AI 提取的知识点</Text>
                            <Tag color="gold" style={{ marginLeft: 8 }}>共 {chapters.length} 个章节</Tag>
                          </Space>
                          <Button
                            icon={<ReloadOutlined />}
                            onClick={() => selectedBook && reparseMutation.mutate(selectedBook.id)}
                            loading={reparseMutation.isPending}
                          >
                            重新提取
                          </Button>
                        </div>

                        {chaptersQ.isLoading ? (
                          <Skeleton active paragraph={{ rows: 8 }} />
                        ) : chapters.length === 0 ? (
                          <EmptyState height={200} description="暂无章节数据" />
                        ) : (
                          chapters.map((ch, idx) => (
                            <Card
                              key={ch.id}
                              size="small"
                              style={{ marginBottom: 16 }}
                              title={
                                <Space>
                                  <Tag color="blue">{idx + 1}</Tag>
                                  <Text strong>{ch.title}</Text>
                                </Space>
                              }
                              styles={{ body: { padding: 16 } }}
                            >
                              <Paragraph style={{ marginBottom: 12 }}>
                                <Text type="secondary">📋 章节概要</Text>
                                <br />
                                <Text style={{ fontSize: 14 }}>
                                  第 {ch.chapter_order} 章 · {ch.char_count} 字符
                                </Text>
                              </Paragraph>
                              <Space wrap>
                                {['核心概念', '关键要点', '实战建议', '常见误区'].map((tag) => (
                                  <Tag key={tag} color="geekblue" style={{ padding: '2px 10px' }}>#{tag}</Tag>
                                ))}
                              </Space>
                            </Card>
                          ))
                        )}
                      </>
                    )}
                  </div>
                )}

                {readerMode === 'qa' && (
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                    <div style={{ flex: 1, overflowY: 'auto', padding: 24, background: '#fafafa' }}>
                      {qaMessages.length === 0 && !qaMutation.isPending ? (
                        <EmptyState
                          height={300}
                          image={<QuestionCircleOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
                          description="向 AI 提问，基于书籍内容获取精准回答"
                          extra={
                            <Space direction="vertical" style={{ marginTop: 16 }}>
                              {['这本书的核心观点是什么？', '如何构建有效的交易系统？', '风险管理的关键原则有哪些？'].map((q) => (
                                <Tag
                                  key={q} color="blue"
                                  style={{ cursor: 'pointer', padding: '6px 14px', fontSize: 13 }}
                                  onClick={() => setQaInput(q)}
                                >
                                  💬 {q}
                                </Tag>
                              ))}
                            </Space>
                          }
                        />
                      ) : (
                        <List
                          dataSource={qaMessages}
                          renderItem={(msg, msgIdx) => (
                            <List.Item
                              style={{
                                border: 'none', padding: 0, marginBottom: 20,
                                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex', maxWidth: '80%', alignItems: 'flex-start', gap: 12,
                                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                                }}
                              >
                                <Avatar
                                  size={36}
                                  style={{ background: msg.role === 'user' ? '#1677ff' : '#52c41a', flexShrink: 0 }}
                                >
                                  {msg.role === 'user' ? '我' : 'AI'}
                                </Avatar>
                                <div
                                  style={{
                                    padding: '12px 16px', borderRadius: 12,
                                    background: msg.role === 'user' ? '#1677ff' : '#fff',
                                    color: msg.role === 'user' ? '#fff' : '#1f1f1f',
                                    boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                                    border: msg.role === 'user' ? 'none' : '1px solid #f0f0f0',
                                  }}
                                >
                                  {qaMutation.isPending && msgIdx === qaMessages.length - 1 && msg.role === 'user' && (
                                    <Skeleton active paragraph={{ rows: 2 }} title={false} />
                                  )}
                                  {!(qaMutation.isPending && msgIdx === qaMessages.length - 1 && msg.role === 'user') && (
                                    <>
                                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{msg.content}</div>
                                      {msg.sources && msg.sources.length > 0 && (
                                        <div style={{ marginTop: 12 }}>
                                          <Divider style={{ margin: '8px 0' }} />
                                          <Text type="secondary" style={{ fontSize: 12 }}>📚 来源参考：</Text>
                                          <Space wrap style={{ marginTop: 4 }}>
                                            {msg.sources.map((s, si) => (
                                              <Tag key={si} color="purple" style={{ margin: 0 }}>
                                                {s.chapter || `第${si + 1}章`}
                                                {s.page_num ? ` · P${s.page_num}` : ''}
                                              </Tag>
                                            ))}
                                          </Space>
                                        </div>
                                      )}
                                    </>
                                  )}
                                </div>
                              </div>
                            </List.Item>
                          )}
                        />
                      )}
                    </div>

                    <div style={{ padding: '12px 24px', borderTop: '1px solid #f0f0f0', background: '#fff' }}>
                      <Space.Compact style={{ width: '100%' }}>
                        <TextArea
                          value={qaInput}
                          onChange={(e) => setQaInput(e.target.value)}
                          placeholder="基于书籍内容提问..."
                          autoSize={{ minRows: 1, maxRows: 4 }}
                          onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); handleSendQA(); } }}
                          disabled={qaMutation.isPending || !selectedBook}
                          style={{ resize: 'none' }}
                        />
                        <Button
                          type="primary" icon={<SendOutlined />} onClick={handleSendQA}
                          loading={qaMutation.isPending} disabled={!qaInput.trim() || !selectedBook}
                          style={{ height: 'auto', minHeight: 40 }}
                        >
                          发送
                        </Button>
                      </Space.Compact>
                      <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
                        按 Enter 发送，Shift + Enter 换行
                      </Text>
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
        </Col>
      </Row>

      {/* AI 分析结果弹窗 */}
      <Modal
        title="AI 书籍分析"
        open={analyzeModalOpen}
        onCancel={() => { setAnalyzeModalOpen(false); setAnalyzeResult(null); }}
        width={800}
        footer={!analyzeResult && !analyzeMutation.isPending ? (
          <Button type="primary" onClick={handleStartAnalyze} icon={<BulbOutlined />} size="large">
            开始分析
          </Button>
        ) : null}
      >
        {!analyzeResult ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            {/* 策略选择器 */}
            <Card size="small" title="参考策略（可选）" style={{ marginBottom: 16 }}>
              <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                选择已有的策略作为参考，AI 分析时会综合这些策略的核心理念进行深入分析
              </Text>
              <Select
                mode="multiple"
                allowClear
                placeholder="请选择要参考的策略（可选）"
                style={{ width: '100%' }}
                showSearch
                optionFilterProp="label"
                value={analyzeStrategyIds}
                onChange={setAnalyzeStrategyIds}
                options={(allStrategiesQ.data || []).map(s => ({ label: s.name, value: s.id }))}
                loading={allStrategiesQ.isLoading}
                notFoundContent="暂无策略"
              />
            </Card>

            {analyzeMutation.isPending && (
              <Space direction="vertical" style={{ width: '100%', textAlign: 'center', padding: 40 }}>
                <Spin size="large" />
                <Text>AI 正在分析书籍内容，请稍候...</Text>
                <Text type="secondary">分析过程包括：书籍解读 → 核心概念提取 → 交易系统生成</Text>
              </Space>
            )}
          </Space>
        ) : (
          <Tabs
            items={[
              {
                key: 'analysis',
                label: '书籍分析报告',
                children: (
                  <div style={{ maxHeight: 500, overflowY: 'auto' }}>
                    <Typography>
                      <pre style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.7, fontFamily: 'inherit' }}>
                        {analyzeResult.book_analysis}
                      </pre>
                    </Typography>
                    <Divider />
                    <Title level={5}>核心概念</Title>
                    <Space wrap>
                      {analyzeResult.core_concepts?.map((c: string, i: number) => (
                        <Tag key={i} color="blue">{c}</Tag>
                      ))}
                    </Space>
                    <Divider />
                    <Title level={5}>策略摘要</Title>
                    <Descriptions column={1} bordered size="small">
                      <Descriptions.Item label="策略名称">{analyzeResult.trading_system?.name}</Descriptions.Item>
                      <Descriptions.Item label="策略类型">{analyzeResult.trading_system?.category}</Descriptions.Item>
                      <Descriptions.Item label="交易对">{analyzeResult.trading_system?.symbol}</Descriptions.Item>
                      <Descriptions.Item label="周期">{analyzeResult.trading_system?.timeframe}</Descriptions.Item>
                    </Descriptions>
                  </div>
                ),
              },
              {
                key: 'strategy',
                label: '生成的交易系统',
                children: (
                  <div style={{ maxHeight: 500, overflowY: 'auto' }}>
                    <Title level={5}>入场规则</Title>
                    <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, borderRadius: 6 }}>
                      {JSON.stringify(analyzeResult.trading_system?.entry_rules, null, 2)}
                    </pre>
                    <Title level={5}>出场规则</Title>
                    <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, borderRadius: 6 }}>
                      {JSON.stringify(analyzeResult.trading_system?.exit_rules, null, 2)}
                    </pre>
                    <Title level={5}>仓位管理</Title>
                    <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, borderRadius: 6 }}>
                      {JSON.stringify(analyzeResult.trading_system?.position_sizing, null, 2)}
                    </pre>
                    <Title level={5}>风控规则</Title>
                    <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, borderRadius: 6 }}>
                      {JSON.stringify(analyzeResult.trading_system?.risk_control, null, 2)}
                    </pre>
                  </div>
                ),
              },
              {
                key: 'strategies',
                label: '关联策略',
                children: (
                  <Table
                    dataSource={bookStrategies}
                    rowKey="id"
                    columns={[
                      { title: '名称', dataIndex: 'name' },
                      { title: '状态', dataIndex: 'status', render: (v: string) => <Tag>{v}</Tag> },
                      { title: '创建时间', dataIndex: 'created_at', render: (v: string) => dayjs(v).format('YYYY-MM-DD') },
                      {
                        title: '操作',
                        render: (_: any, record: any) => (
                          <Button type="link" onClick={() => window.open(`/strategies?id=${record.id}`, '_blank')}>
                            查看详情
                          </Button>
                        ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        )}
      </Modal>

      <CrudModal<BookCreateData>
        open={createModalOpen}
        mode="create"
        entityName="书籍"
        onOk={async (values) => { await createMutation.mutateAsync(values); }}
        onCancel={() => { setCreateModalOpen(false); }}
      >
        <Form.Item name="title" label="书名" rules={[{ required: true, message: '请输入书名' }]}>
          <Input placeholder="请输入书名" />
        </Form.Item>
        <Form.Item name="author" label="作者">
          <Input placeholder="请输入作者" />
        </Form.Item>
        <Form.Item name="category" label="类别">
          <Select
            placeholder="请选择类别"
            options={CATEGORY_OPTIONS.filter((o) => o.value !== undefined).map((o) => ({ label: o.label, value: o.value }))}
          />
        </Form.Item>
        <Form.Item name="tags" label="标签">
          <Select mode="tags" placeholder="输入标签后回车" style={{ width: '100%' }} tokenSeparators={[',']} />
        </Form.Item>
        <Form.Item name="description" label="简介">
          <TextArea rows={4} placeholder="请输入书籍简介" />
        </Form.Item>
      </CrudModal>
    </PageContainer>
  );
};

export default BooksPage;