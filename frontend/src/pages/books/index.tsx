import { useMemo, useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Col,
  Row,
  Segmented,
  Space,
  Tag,
  Typography,
  Input,
  Select,
  Button,
  Upload,
  Progress,
  Tree,
  List,
  Avatar,
  Skeleton,
  Form,
  message,
  Divider,
} from 'antd';
import type { UploadProps, TreeDataNode } from 'antd';
import {
  UploadOutlined,
  PlusOutlined,
  DeleteOutlined,
  LeftOutlined,
  RightOutlined,
  EditOutlined,
  SendOutlined,
  ReloadOutlined,
  BookOutlined,
  BulbOutlined,
  QuestionCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import {
  PageContainer,
  EmptyState,
  ConfirmButton,
  CrudModal,
} from '@/components/Common';
import { bookApi } from '@/api';
import type { Book, BookCreateData, ParseStatus, BookQAResponse } from '@/types';

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

const SYNTHETIC_CHAPTERS = [
  { id: 'ch1', title: '第一章 交易基础概论', order_index: 1 },
  { id: 'ch2', title: '第二章 市场结构与参与者', order_index: 2 },
  { id: 'ch3', title: '第三章 K线与形态分析', order_index: 3 },
  { id: 'ch4', title: '第四章 技术指标详解', order_index: 4 },
  { id: 'ch5', title: '第五章 趋势与支撑阻力', order_index: 5 },
  { id: 'ch6', title: '第六章 风险管理框架', order_index: 6 },
  { id: 'ch7', title: '第七章 交易系统构建', order_index: 7 },
  { id: 'ch8', title: '第八章 交易心理修炼', order_index: 8 },
];

const SAMPLE_PARAGRAPHS = [
  '交易是一门需要长期学习和实践的艺术。成功的交易者不仅需要掌握技术分析和基础分析的工具，更需要建立一套完整的交易系统和严格的纪律。在本章中，我们将从最基础的概念开始，逐步构建起交易的知识框架。',
  '市场的存在源于买方和卖方的分歧。每一笔交易的背后，都有一个看多者和一个看空者。理解市场参与者的动机和行为模式，是做出明智交易决策的前提。机构投资者、对冲基金、零售交易者在市场中扮演着不同的角色。',
  'K线是技术分析的基石。一根K线包含了开盘价、最高价、最低价和收盘价四个关键信息。不同形态的K线组合，往往预示着市场情绪的转变。锤头、吞没、十字星等经典形态，经过数十年的验证仍然有效。',
  '移动平均线、MACD、RSI、布林带……技术指标种类繁多，但核心思想都是通过数学变换来捕捉市场的趋势和波动。重要的不是指标的数量，而是对少数几个指标的深刻理解和灵活运用。',
  '趋势是交易者最好的朋友。识别趋势、跟随趋势、在趋势结束时离场，这是顺势交易的三部曲。支撑位和阻力位则是市场价格的"记忆"，它们记录了过去多空双方激烈交战的区域。',
  '风险管理是交易的生命线。无论你的分析多么准确，只要没有做好风险管理，一次重大的亏损就可能让你之前的所有努力付诸东流。仓位管理、止损设置、分散投资，是风险管理的三大支柱。',
  '一个完善的交易系统应该包含：入场规则、出场规则、仓位规则、止损止盈规则。系统的价值不在于它的完美，而在于它的一致性。严格执行一个简单但正期望值的系统，远胜过随意的"灵感交易"。',
  '交易到最后，比拼的不是技术，而是心态。恐惧让我们过早离场，贪婪让我们过度持仓，侥幸让我们不愿止损。认识自己的情绪弱点，并通过纪律和规则来约束它们，是交易者走向成熟的必由之路。',
];

const generateId = () => Math.random().toString(36).slice(2, 10);

const BooksPage = () => {
  const queryClient = useQueryClient();

  const [keyword, setKeyword] = useState<string>('');
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [parseStatus, setParseStatus] = useState<ParseStatus | undefined>(undefined);

  const [selectedBook, setSelectedBook] = useState<Book | null>(null);
  const [readerMode, setReaderMode] = useState<ReaderMode>('reader');
  const [fontSize, setFontSize] = useState<FontSize>('medium');
  const [currentChapterId, setCurrentChapterId] = useState<string>('ch1');

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [noteInputVisible, setNoteInputVisible] = useState<number | null>(null);
  const [noteContent, setNoteContent] = useState('');

  const [qaInput, setQaInput] = useState('');
  const [qaMessages, setQaMessages] = useState<QAMessage[]>([]);
  const [parseProgress, setParseProgress] = useState<number>(0);

  const booksQ = useQuery({
    queryKey: ['books', 'list', keyword, category, parseStatus],
    queryFn: () =>
      bookApi.getList({
        keyword: keyword || undefined,
        category,
        parse_status: parseStatus,
      }),
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

  const uploadMutation = useMutation({
    mutationFn: (formData: FormData) => bookApi.upload(formData),
    onSuccess: (book) => {
      message.success('书籍上传成功，正在自动解析...');
      queryClient.invalidateQueries({ queryKey: ['books', 'list'] });
      // 上传后自动触发解析
      if (book?.id) {
        parseMutation.mutate(book.id);
      }
    },
    onError: () => message.error('书籍上传失败'),
  });

  const parseMutation = useMutation({
    mutationFn: (id: string) => bookApi.parseContent(id),
    onSuccess: () => {
      message.success('解析任务已提交');
      queryClient.invalidateQueries({ queryKey: ['books', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['books', 'parse-progress'] });
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
    onSuccess: () => {
      message.success('重新解析任务已提交');
      queryClient.invalidateQueries({ queryKey: ['books', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['books', 'parse-progress'] });
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

  const qaMutation = useMutation({
    mutationFn: (params: { bookId: string; question: string }) =>
      bookApi.qa(params.bookId, params.question),
    onSuccess: (res, vars) => {
      const userMsg: QAMessage = {
        id: generateId(),
        role: 'user',
        content: vars.question,
      };
      const assistantMsg: QAMessage = {
        id: generateId(),
        role: 'assistant',
        content: res.answer,
        sources: res.sources,
      };
      setQaMessages((prev) => [...prev, userMsg, assistantMsg]);
    },
    onError: () => {
      message.error('问答失败');
    },
  });

  const createNoteMutation = useMutation({
    mutationFn: (params: { bookId: string; data: { content: string; highlight_text?: string } }) =>
      bookApi.createNote(params.bookId, params.data),
    onSuccess: () => {
      message.success('笔记保存成功');
      setNoteInputVisible(null);
      setNoteContent('');
      queryClient.invalidateQueries({ queryKey: ['books', 'notes'] });
    },
    onError: () => message.error('笔记保存失败'),
  });

  const books = booksQ.data || [];
  const detail = bookDetailQ.data || selectedBook;
  const notes = notesQ.data || [];

  const chapterTree: TreeDataNode[] = useMemo(() => {
    return SYNTHETIC_CHAPTERS.map((c) => ({
      key: c.id,
      title: c.title,
      isLeaf: true,
    }));
  }, []);

  const currentChapterIndex = useMemo(() => {
    return SYNTHETIC_CHAPTERS.findIndex((c) => c.id === currentChapterId);
  }, [currentChapterId]);

  const currentChapter = SYNTHETIC_CHAPTERS[currentChapterIndex];

  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.pdf,.epub,.txt,.md,.docx',
    showUploadList: false,
    customRequest: async (options) => {
      const formData = new FormData();
      if (options.file) {
        formData.append('file', options.file);
      }
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
    setCurrentChapterId('ch1');
    setReaderMode('reader');
  };

  const handlePrevChapter = () => {
    if (currentChapterIndex > 0) {
      setCurrentChapterId(SYNTHETIC_CHAPTERS[currentChapterIndex - 1].id);
    }
  };

  const handleNextChapter = () => {
    if (currentChapterIndex < SYNTHETIC_CHAPTERS.length - 1) {
      setCurrentChapterId(SYNTHETIC_CHAPTERS[currentChapterIndex + 1].id);
    }
  };

  const handleSendQA = async () => {
    if (!qaInput.trim() || !selectedBook) return;
    const question = qaInput.trim();
    setQaInput('');
    const pendingMsg: QAMessage = {
      id: generateId(),
      role: 'user',
      content: question,
    };
    setQaMessages((prev) => [...prev, pendingMsg]);
    await qaMutation.mutateAsync({ bookId: selectedBook.id, question });
  };

  const handleSaveNote = (paragraphIdx: number) => {
    if (!noteContent.trim() || !selectedBook) return;
    createNoteMutation.mutate({
      bookId: selectedBook.id,
      data: {
        content: noteContent.trim(),
        highlight_text: SAMPLE_PARAGRAPHS[paragraphIdx]?.slice(0, 50),
      },
    });
  };

  const renderCover = (book: Book) => {
    if (book.cover_image_url) {
      return (
        <div
          style={{
            height: 120,
            backgroundImage: `url(${book.cover_image_url})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            borderTopLeftRadius: 8,
            borderTopRightRadius: 8,
          }}
        />
      );
    }
    return (
      <div
        style={{
          height: 120,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderTopLeftRadius: 8,
          borderTopRightRadius: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: 36,
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

  const fontSizeConf = FONT_SIZE_MAP[fontSize];

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
            onConfirm={async () => {
              await deleteMutation.mutateAsync(selectedBook.id);
            }}
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
                    style={{ width: '100%' }}
                    placeholder="类别"
                    value={category}
                    onChange={setCategory}
                    options={CATEGORY_OPTIONS.filter((o) => o.value !== undefined).map((o) => ({
                      label: o.label,
                      value: o.value,
                    }))}
                    allowClear
                  />
                </Col>
                <Col span={12}>
                  <Select
                    style={{ width: '100%' }}
                    placeholder="解析状态"
                    value={parseStatus}
                    onChange={(v) => setParseStatus(v as ParseStatus | undefined)}
                    options={PARSE_STATUS_OPTIONS.filter((o) => o.value !== undefined).map((o) => ({
                      label: o.label,
                      value: o.value,
                    }))}
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
                <EmptyState
                  description="暂无书籍，上传或新增第一本吧"
                  height={260}
                />
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
                            borderRadius: 8,
                            overflow: 'hidden',
                            transition: 'all 0.2s',
                          }}
                        >
                          {renderCover(book)}
                          <div style={{ padding: 12 }}>
                            <Text
                              strong
                              style={{
                                display: '-webkit-box',
                                WebkitLineClamp: 1,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                fontSize: 14,
                                marginBottom: 4,
                              }}
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
                              percent={Math.round(book.reading_progress * 100)}
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
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
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
                            解析中 {detail?.parse_progress ? `${Math.round(detail.parse_progress * 100)}%` : ''}
                          </Tag>
                        )}
                        {detail?.parse_status === 'failed' && (
                          <Tag color="error">解析失败</Tag>
                        )}
                        {detail?.parse_status === 'completed' && (
                          <Tag color="success">已解析</Tag>
                        )}
                      </Space>
                    </div>
                    <Space>
                      {detail?.parse_status === 'completed' && (
                        <Button
                          icon={<ReloadOutlined />}
                          onClick={() => selectedBook && reparseMutation.mutate(selectedBook.id)}
                          loading={reparseMutation.isPending}
                          size="small"
                        >
                          重新解析
                        </Button>
                      )}
                      {detail?.parse_status === 'failed' && (
                        <Button
                          icon={<ReloadOutlined />}
                          onClick={() => selectedBook && parseMutation.mutate(selectedBook.id)}
                          loading={parseMutation.isPending}
                          size="small"
                        >
                          重新解析
                        </Button>
                      )}
                    </Space>
                  </Space>
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
                    <div
                      style={{
                        padding: '12px 24px',
                        borderBottom: '1px solid #f0f0f0',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: 8,
                      }}
                    >
                      <Space>
                        <Button
                          icon={<LeftOutlined />}
                          onClick={handlePrevChapter}
                          disabled={currentChapterIndex <= 0}
                          size="small"
                        >
                          上一章
                        </Button>
                        <Text strong style={{ fontSize: fontSizeConf.title - 2 }}>
                          {currentChapter?.title}
                        </Text>
                        <Button
                          icon={<RightOutlined />}
                          onClick={handleNextChapter}
                          disabled={currentChapterIndex >= SYNTHETIC_CHAPTERS.length - 1}
                          size="small"
                        >
                          下一章
                        </Button>
                      </Space>
                      <Segmented<FontSize>
                        size="small"
                        value={fontSize}
                        onChange={setFontSize}
                        options={FONT_SIZE_OPTIONS}
                      />
                    </div>

                    <Row style={{ flex: 1, overflow: 'hidden', margin: 0 }}>
                      <Col
                        xs={24}
                        sm={8}
                        md={6}
                        lg={5}
                        xl={4}
                        style={{
                          borderRight: '1px solid #f0f0f0',
                          overflowY: 'auto',
                          height: '100%',
                          padding: '16px 8px',
                        }}
                      >
                        <Text type="secondary" style={{ padding: '0 8px', fontSize: 12 }}>
                          章节目录
                        </Text>
                        <Tree
                          treeData={chapterTree}
                          defaultExpandAll
                          selectedKeys={[currentChapterId]}
                          onSelect={(keys) => setCurrentChapterId(String(keys[0]))}
                          style={{ marginTop: 8, background: 'transparent' }}
                          showLine={{ showLeafIcon: false }}
                          blockNode
                        />
                        {notes.length > 0 && (
                          <>
                            <Divider style={{ margin: '16px 0 8px' }} />
                            <Text type="secondary" style={{ padding: '0 8px', fontSize: 12 }}>
                              我的笔记 ({notes.length})
                            </Text>
                            <List
                              size="small"
                              dataSource={notes}
                              style={{ marginTop: 8 }}
                              renderItem={(note) => (
                                <List.Item style={{ padding: '6px 8px' }}>
                                  <Text
                                    ellipsis={{ tooltip: note.content }}
                                    style={{ fontSize: 12 }}
                                  >
                                    📝 {note.content}
                                  </Text>
                                </List.Item>
                              )}
                            />
                          </>
                        )}
                      </Col>

                      <Col
                        xs={24}
                        sm={16}
                        md={18}
                        lg={19}
                        xl={20}
                        style={{
                          overflowY: 'auto',
                          height: '100%',
                          padding: '24px 40px',
                          background: '#fefefe',
                        }}
                      >
                        <Title level={4} style={{ marginBottom: 24, color: '#1f1f1f' }}>
                          {currentChapter?.title}
                        </Title>
                        <div style={{ maxWidth: 800 }}>
                          {SAMPLE_PARAGRAPHS.map((p, idx) => (
                            <div
                              key={idx}
                              style={{
                                position: 'relative',
                                marginBottom: 24,
                                paddingRight: 40,
                              }}
                            >
                              <Paragraph
                                style={{
                                  fontSize: fontSizeConf.body,
                                  lineHeight: fontSizeConf.lineHeight,
                                  textIndent: '2em',
                                  margin: 0,
                                  color: '#262626',
                                }}
                              >
                                {p}
                              </Paragraph>
                              <Button
                                type="text"
                                size="small"
                                icon={<EditOutlined />}
                                style={{
                                  position: 'absolute',
                                  right: 0,
                                  top: 0,
                                  color: '#bfbfbf',
                                }}
                                onClick={() => {
                                  setNoteInputVisible(noteInputVisible === idx ? null : idx);
                                  setNoteContent('');
                                }}
                              />
                              {noteInputVisible === idx && (
                                <div
                                  style={{
                                    marginTop: 12,
                                    padding: 12,
                                    background: '#fffbe6',
                                    border: '1px solid #ffe58f',
                                    borderRadius: 6,
                                  }}
                                >
                                  <TextArea
                                    rows={3}
                                    placeholder="记录学习笔记..."
                                    value={noteContent}
                                    onChange={(e) => setNoteContent(e.target.value)}
                                    autoFocus
                                    style={{ marginBottom: 8 }}
                                  />
                                  <Space>
                                    <Button
                                      type="primary"
                                      size="small"
                                      onClick={() => handleSaveNote(idx)}
                                      loading={createNoteMutation.isPending}
                                    >
                                      保存笔记
                                    </Button>
                                    <Button
                                      size="small"
                                      onClick={() => {
                                        setNoteInputVisible(null);
                                        setNoteContent('');
                                      }}
                                    >
                                      取消
                                    </Button>
                                  </Space>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </Col>
                    </Row>
                  </>
                )}

                {readerMode === 'knowledge' && (
                  <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 16,
                      }}
                    >
                      <Space>
                        <BulbOutlined style={{ color: '#faad14', fontSize: 20 }} />
                        <Text strong style={{ fontSize: 16 }}>
                          AI 提取的知识点
                        </Text>
                        <Tag color="gold" style={{ marginLeft: 8 }}>
                          共 {SYNTHETIC_CHAPTERS.length} 个章节
                        </Tag>
                      </Space>
                      <Button
                        icon={<ReloadOutlined />}
                        onClick={() => selectedBook && reparseMutation.mutate(selectedBook.id)}
                        loading={reparseMutation.isPending}
                      >
                        重新提取
                      </Button>
                    </div>

                    {SYNTHETIC_CHAPTERS.map((ch, idx) => (
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
                          <Text type="secondary">📋 本章摘要：</Text>
                          <br />
                          <Text style={{ fontSize: 14 }}>
                            {SAMPLE_PARAGRAPHS[idx]?.slice(0, 120)}...
                          </Text>
                        </Paragraph>
                        <Space wrap>
                          {['核心概念', '关键要点', '实战建议', '常见误区'].map((tag, i) => (
                            <Tag key={i} color="geekblue" style={{ padding: '2px 10px' }}>
                              #{tag}
                            </Tag>
                          ))}
                        </Space>
                        <Divider style={{ margin: '12px 0' }} />
                        <div style={{ fontSize: 13, color: '#595959' }}>
                          <div style={{ marginBottom: 6 }}>
                            <b>🔑 关键知识点 1：</b> 理解市场结构与价格行为的基本关系
                          </div>
                          <div style={{ marginBottom: 6 }}>
                            <b>🔑 关键知识点 2：</b> 掌握技术分析的三大假设及其应用场景
                          </div>
                          <div>
                            <b>🔑 关键知识点 3：</b> 学会识别并过滤无效的交易信号
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                )}

                {readerMode === 'qa' && (
                  <div
                    style={{
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        flex: 1,
                        overflowY: 'auto',
                        padding: 24,
                        background: '#fafafa',
                      }}
                    >
                      {qaMessages.length === 0 && !qaMutation.isPending ? (
                        <EmptyState
                          height={300}
                          image={<QuestionCircleOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
                          description="向 AI 提问，基于书籍内容获取精准回答"
                          extra={
                            <Space direction="vertical" style={{ marginTop: 16 }}>
                              {[
                                '这本书的核心观点是什么？',
                                '如何构建有效的交易系统？',
                                '风险管理的关键原则有哪些？',
                              ].map((q) => (
                                <Tag
                                  key={q}
                                  color="blue"
                                  style={{
                                    cursor: 'pointer',
                                    padding: '6px 14px',
                                    fontSize: 13,
                                  }}
                                  onClick={() => {
                                    setQaInput(q);
                                  }}
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
                                border: 'none',
                                padding: 0,
                                marginBottom: 20,
                                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex',
                                  maxWidth: '80%',
                                  alignItems: 'flex-start',
                                  gap: 12,
                                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                                }}
                              >
                                <Avatar
                                  size={36}
                                  style={{
                                    background: msg.role === 'user' ? '#1677ff' : '#52c41a',
                                    flexShrink: 0,
                                  }}
                                >
                                  {msg.role === 'user' ? '我' : 'AI'}
                                </Avatar>
                                <div
                                  style={{
                                    padding: '12px 16px',
                                    borderRadius: 12,
                                    background: msg.role === 'user' ? '#1677ff' : '#fff',
                                    color: msg.role === 'user' ? '#fff' : '#1f1f1f',
                                    boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                                    border: msg.role === 'user' ? 'none' : '1px solid #f0f0f0',
                                  }}
                                >
                                  {qaMutation.isPending &&
                                    msgIdx === qaMessages.length - 1 &&
                                    msg.role === 'user' && <Skeleton active paragraph={{ rows: 2 }} title={false} />}
                                  {!(qaMutation.isPending && msgIdx === qaMessages.length - 1 && msg.role === 'user') && (
                                    <>
                                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
                                        {msg.content}
                                      </div>
                                      {msg.sources && msg.sources.length > 0 && (
                                        <div style={{ marginTop: 12 }}>
                                          <Divider style={{ margin: '8px 0' }} />
                                          <Text type="secondary" style={{ fontSize: 12 }}>
                                            📚 来源参考：
                                          </Text>
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

                    <div
                      style={{
                        padding: '12px 24px',
                        borderTop: '1px solid #f0f0f0',
                        background: '#fff',
                      }}
                    >
                      <Space.Compact style={{ width: '100%' }}>
                        <TextArea
                          value={qaInput}
                          onChange={(e) => setQaInput(e.target.value)}
                          placeholder="基于书籍内容提问..."
                          autoSize={{ minRows: 1, maxRows: 4 }}
                          onPressEnter={(e) => {
                            if (!e.shiftKey) {
                              e.preventDefault();
                              handleSendQA();
                            }
                          }}
                          disabled={qaMutation.isPending || !selectedBook}
                          style={{ resize: 'none' }}
                        />
                        <Button
                          type="primary"
                          icon={<SendOutlined />}
                          onClick={handleSendQA}
                          loading={qaMutation.isPending}
                          disabled={!qaInput.trim() || !selectedBook}
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

      <CrudModal<BookCreateData>
        open={createModalOpen}
        mode="create"
        entityName="书籍"
        onOk={async (values) => {
          await createMutation.mutateAsync(values);
        }}
        onCancel={() => {
          setCreateModalOpen(false);
        }}
      >
        <Form.Item
          name="title"
          label="书名"
          rules={[{ required: true, message: '请输入书名' }]}
        >
          <Input placeholder="请输入书名" />
        </Form.Item>
        <Form.Item name="author" label="作者">
          <Input placeholder="请输入作者" />
        </Form.Item>
        <Form.Item name="category" label="类别">
          <Select
            placeholder="请选择类别"
            options={CATEGORY_OPTIONS.filter((o) => o.value !== undefined).map((o) => ({
              label: o.label,
              value: o.value,
            }))}
          />
        </Form.Item>
        <Form.Item name="tags" label="标签">
          <Select
            mode="tags"
            placeholder="输入标签后回车"
            style={{ width: '100%' }}
            tokenSeparators={[',']}
          />
        </Form.Item>
        <Form.Item name="description" label="简介">
          <TextArea rows={4} placeholder="请输入书籍简介" />
        </Form.Item>
      </CrudModal>
    </PageContainer>
  );
};

export default BooksPage;
