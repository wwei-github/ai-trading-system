import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Upload,
  message,
  Result,
  Alert,
  Divider,
} from 'antd';
import {
  PlusOutlined,
  ImportOutlined,
  ExportOutlined,
  InboxOutlined,
  EditOutlined,
  SearchOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  PageContainer,
  SearchForm,
  CrudModal,
  AmountText,
  ConfirmButton,
  EmptyState,
} from '@/components/Common';
import { tradeApi, accountApi } from '@/api';
import type {
  Trade,
  TradeFormData,
  TradeListParams,
  TradeTag,
  TradeDirection,
  BatchImportResult,
} from '@/types';
import { TRADE_DIRECTION_MAP } from '@/types/trades';

const { RangePicker } = DatePicker;
const { Dragger } = Upload;

type SearchValues = Partial<TradeListParams> & { time_range?: [dayjs.Dayjs, dayjs.Dayjs] };

const TradesPage = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useState<SearchValues>({
    page: 1,
    page_size: 15,
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [currentRecord, setCurrentRecord] = useState<Trade | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importResult, setImportResult] = useState<BatchImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [tagFilter, setTagFilter] = useState<number | null>(null);

  // ========== 查询列表 ==========
  const actualQueryParams: TradeListParams = useMemo(() => {
    const { time_range, ...rest } = searchParams;
    return {
      ...rest,
      start_time: time_range?.[0]?.format('YYYY-MM-DD'),
      end_time: time_range?.[1]?.format('YYYY-MM-DD'),
      tag_id: tagFilter || undefined,
    };
  }, [searchParams, tagFilter]);

  const { data, isLoading } = useQuery({
    queryKey: ['trades', 'list', actualQueryParams],
    queryFn: () => tradeApi.getList(actualQueryParams),
  });

  // 账号下拉（用于筛选和表单）
  const { data: accountsData } = useQuery({
    queryKey: ['accounts', 'select'],
    queryFn: () => accountApi.getList({ page: 1, page_size: 100 }),
  });
  const accountOptions = useMemo(
    () =>
      (accountsData?.items || []).map((a) => ({
        value: a.id,
        label: a.alias,
      })),
    [accountsData],
  );

  // ========== 标签列表 ==========
  const { data: tagsData } = useQuery({
    queryKey: ['trades', 'tags'],
    queryFn: () => tradeApi.getTags(),
  });

  const createTagMutation = useMutation({
    mutationFn: (name: string) => tradeApi.createTag({ name }),
    onSuccess: () => {
      message.success('标签已创建');
      queryClient.invalidateQueries({ queryKey: ['trades', 'tags'] });
    },
  });

  // ========== 新增/编辑 ==========
  const createMutation = useMutation({
    mutationFn: (d: TradeFormData) => tradeApi.create(d),
    onSuccess: () => {
      message.success('录入成功');
      queryClient.invalidateQueries({ queryKey: ['trades'] });
      setModalOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<TradeFormData> }) =>
      tradeApi.update(id, data),
    onSuccess: () => {
      message.success('修改成功');
      queryClient.invalidateQueries({ queryKey: ['trades'] });
      setModalOpen(false);
    },
  });

  // ========== 删除 ==========
  const deleteMutation = useMutation({
    mutationFn: (id: number) => tradeApi.delete(id),
    onSuccess: () => {
      message.success('删除成功');
      queryClient.invalidateQueries({ queryKey: ['trades'] });
    },
  });

  // ========== 导出 ==========
  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await tradeApi.export(actualQueryParams);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `交易记录_${dayjs().format('YYYYMMDD_HHmmss')}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch (err) {
      message.error('导出失败');
    } finally {
      setExporting(false);
    }
  };

  // ========== 导入 ==========
  const handleImportFile = async (file: File) => {
    setImporting(true);
    setImportResult(null);
    try {
      const result = await tradeApi.batchImport(file);
      setImportResult(result);
      if (result.failed === 0) {
        message.success(`导入成功：${result.success} 条`);
      } else {
        message.warning(`导入完成：成功 ${result.success} 条，失败 ${result.failed} 条`);
      }
      queryClient.invalidateQueries({ queryKey: ['trades'] });
    } catch (err) {
      message.error('导入失败');
    } finally {
      setImporting(false);
    }
    return false; // 阻止默认上传行为
  };

  // ========== 搜索条件 ==========
  const searchFields = useMemo(
    () => [
      {
        name: 'account_id',
        label: '账号',
        element: (
          <Select
            allowClear
            placeholder="请选择账号"
            options={accountOptions}
            showSearch
            optionFilterProp="label"
          />
        ),
      },
      {
        name: 'symbol',
        label: '币种',
        element: <Input allowClear placeholder="如：BTC/USDT" prefix={<SearchOutlined />} />,
      },
      {
        name: 'direction',
        label: '方向',
        element: (
          <Select allowClear placeholder="全部">
            {Object.entries(TRADE_DIRECTION_MAP).map(([k, v]) => (
              <Select.Option key={k} value={k}>
                <span style={{ color: v.color, fontWeight: 500 }}>{v.text}</span>
              </Select.Option>
            ))}
          </Select>
        ),
      },
      {
        name: 'time_range',
        label: '时间范围',
        element: (
          <RangePicker
            style={{ width: '100%' }}
            format="YYYY-MM-DD"
            placeholder={['开始日期', '结束日期']}
          />
        ),
      },
      {
        name: 'keyword',
        label: '关键字',
        element: <Input allowClear placeholder="币种/备注/账号" prefix={<SearchOutlined />} />,
      },
    ],
    [accountOptions],
  );

  // ========== 表格列 ==========
  const columns = useMemo(
    () => [
      {
        title: '交易时间',
        dataIndex: 'trade_time',
        key: 'trade_time',
        width: 170,
        sorter: (a, b) => a.trade_time.localeCompare(b.trade_time),
        render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
      },
      {
        title: '账号',
        dataIndex: 'account_alias',
        key: 'account_alias',
        width: 160,
        render: (v?: string) => <Tag color="geekblue">{v || '-'}</Tag>,
      },
      {
        title: '币种',
        dataIndex: 'symbol',
        key: 'symbol',
        width: 120,
        render: (v: string) => <strong>{v}</strong>,
      },
      {
        title: '方向',
        dataIndex: 'direction',
        key: 'direction',
        width: 80,
        render: (v: TradeDirection) => (
          <span
            style={{
              color: TRADE_DIRECTION_MAP[v].color,
              fontWeight: 600,
            }}
          >
            {TRADE_DIRECTION_MAP[v].text}
          </span>
        ),
      },
      {
        title: '数量',
        dataIndex: 'amount',
        key: 'amount',
        width: 130,
        align: 'right' as const,
        render: (v: number) => <AmountText value={v} precision={4} fontWeight={500} />,
      },
      {
        title: '价格',
        dataIndex: 'price',
        key: 'price',
        width: 140,
        align: 'right' as const,
        render: (v: number) => <AmountText value={v} precision={v > 100 ? 2 : 4} />,
      },
      {
        title: '金额',
        dataIndex: 'total',
        key: 'total',
        width: 150,
        align: 'right' as const,
        render: (v: number) => (
          <AmountText value={v} suffix=" USDT" fontWeight={600} precision={2} />
        ),
      },
      {
        title: '手续费',
        dataIndex: 'fee',
        key: 'fee',
        width: 110,
        align: 'right' as const,
        render: (v: number, rec: Trade) => (
          <AmountText value={v} suffix={rec.fee_currency || ''} precision={6} />
        ),
      },
      {
        title: '盈亏',
        dataIndex: 'profit',
        key: 'profit',
        width: 130,
        align: 'right' as const,
        render: (v?: number) =>
          v !== undefined ? (
            <AmountText value={v} colored suffix=" USDT" showSign fontWeight={600} />
          ) : (
            <span style={{ color: '#bfbfbf' }}>—</span>
          ),
      },
      {
        title: '标签',
        dataIndex: 'tags',
        key: 'tags',
        width: 180,
        render: (tags?: TradeTag[]) =>
          tags && tags.length > 0 ? (
            <Space size={[4, 4]} wrap>
              {tags.map((t) => (
                <Tag
                  key={t.id}
                  color={t.color}
                  style={{ cursor: 'pointer', margin: 2 }}
                  onClick={() => setTagFilter((prev) => (prev === t.id ? null : t.id))}
                >
                  {t.name}
                </Tag>
              ))}
            </Space>
          ) : null,
      },
      {
        title: '备注',
        dataIndex: 'remark',
        key: 'remark',
        width: 150,
        ellipsis: true,
        render: (v?: string) => (
          <Tooltip title={v} placement="topLeft">
            <span style={{ color: '#8c8c8c' }}>{v || '-'}</span>
          </Tooltip>
        ),
      },
      {
        title: '操作',
        key: 'actions',
        width: 130,
        fixed: 'right' as const,
        render: (_: any, record: Trade) => (
          <Space size="small">
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                setCurrentRecord(record);
                setModalMode('edit');
                setModalOpen(true);
              }}
            >
              编辑
            </Button>
            <ConfirmButton
              label="删除"
              type="link"
              size="small"
              title="确认删除该条交易记录？"
              onConfirm={() => deleteMutation.mutateAsync(record.id)}
            />
          </Space>
        ),
      },
    ],
    [deleteMutation],
  );

  // ========== 表单提交 ==========
  const handleModalSubmit = async (values: any) => {
    const payload: TradeFormData = {
      ...values,
      trade_time: values.trade_time
        ? dayjs(values.trade_time).format('YYYY-MM-DD HH:mm:ss')
        : dayjs().format('YYYY-MM-DD HH:mm:ss'),
    };
    if (modalMode === 'create') {
      await createMutation.mutateAsync(payload);
    } else if (currentRecord) {
      await updateMutation.mutateAsync({ id: currentRecord.id, data: payload });
    }
  };

  // 弹窗表单初始值
  const modalInitialValues: any = useMemo(() => {
    if (!currentRecord) {
      return {
        direction: 'buy',
        fee_currency: 'USDT',
        trade_time: dayjs(),
      };
    }
    return {
      account_id: currentRecord.account_id,
      symbol: currentRecord.symbol,
      direction: currentRecord.direction,
      amount: currentRecord.amount,
      price: currentRecord.price,
      fee: currentRecord.fee,
      fee_currency: currentRecord.fee_currency,
      trade_time: dayjs(currentRecord.trade_time),
      tag_ids: currentRecord.tags?.map((t) => t.id) || [],
      remark: currentRecord.remark,
    };
  }, [currentRecord]);

  // ========== 自定义标签（Select dropdownRender） ==========
  const tagDropdownRender = (menu: React.ReactNode) => {
    const [input, setInput] = useState('');
    return (
      <>
        {menu}
        <Divider style={{ margin: '8px 0' }} />
        <Space style={{ padding: '0 8px 8px', width: '100%' }}>
          <Input
            size="small"
            placeholder="新标签名称"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={async () => {
              if (input.trim()) {
                await createTagMutation.mutateAsync(input.trim());
                setInput('');
              }
            }}
            style={{ flex: 1 }}
          />
          <Button
            size="small"
            type="primary"
            disabled={!input.trim()}
            loading={createTagMutation.isPending}
            onClick={async () => {
              if (input.trim()) {
                await createTagMutation.mutateAsync(input.trim());
                setInput('');
              }
            }}
          >
            新增
          </Button>
        </Space>
      </>
    );
  };

  return (
    <PageContainer
      breadcrumbs={[{ title: '交易记录' }]}
      title="交易记录管理"
      description={
        tagFilter ? (
          <Tag
            color="blue"
            closable
            onClose={() => setTagFilter(null)}
            style={{ marginInlineStart: 0 }}
          >
            按标签筛选：{tagsData?.find((t) => t.id === tagFilter)?.name}
          </Tag>
        ) : (
          '交易记录全生命周期管理：录入、查询、批量导入导出与标签化管理'
        )
      }
      extra={
        <Space>
          <Button
            icon={<ImportOutlined />}
            onClick={() => {
              setImportModalOpen(true);
              setImportResult(null);
            }}
          >
            批量导入
          </Button>
          <Button
            icon={<ExportOutlined />}
            onClick={handleExport}
            loading={exporting}
          >
            批量导出
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setCurrentRecord(null);
              setModalMode('create');
              setModalOpen(true);
            }}
          >
            新增交易
          </Button>
        </Space>
      }
    >
      {/* 筛选区 */}
      <div style={{ marginBottom: 16 }}>
        <SearchForm
          fields={searchFields}
          columns={3}
          initialValues={searchParams}
          onSearch={(values: SearchValues) => {
            setSearchParams((prev) => ({
              ...prev,
              ...values,
              page: 1,
            }));
          }}
          extraButtons={
            tagFilter ? (
              <Button onClick={() => setTagFilter(null)}>
                清除标签筛选
              </Button>
            ) : undefined
          }
        />
      </div>

      {/* 表格 */}
      <Table<Trade>
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={data?.items || []}
        scroll={{ x: 1650 }}
        size="middle"
        pagination={{
          current: searchParams.page,
          pageSize: searchParams.page_size,
          total: data?.total || 0,
          showSizeChanger: true,
          showQuickJumper: true,
          pageSizeOptions: ['15', '30', '50', '100'],
          showTotal: (total, range) =>
            `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
          onChange: (page, pageSize) => {
            setSearchParams((prev) => ({ ...prev, page, page_size: pageSize }));
          },
        }}
        locale={{
          emptyText: <EmptyState description="暂无交易记录，点击右上角新增交易" />,
        }}
      />

      {/* 新增/编辑弹窗 */}
      <CrudModal
        open={modalOpen}
        mode={modalMode}
        entityName="交易记录"
        initialValues={modalInitialValues}
        onOk={handleModalSubmit}
        onCancel={() => setModalOpen(false)}
        modalProps={{ width: 720 }}
      >
        <Space.Compact style={{ width: '100%', display: 'flex' }}>
          <Form.Item
            label="账号"
            name="account_id"
            rules={[{ required: true, message: '请选择账号' }]}
            style={{ flex: 1, marginRight: 12 }}
          >
            <Select
              placeholder="请选择交易所账号"
              options={accountOptions}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
          <Form.Item
            label="币种"
            name="symbol"
            rules={[
              { required: true, message: '请输入币种' },
              { pattern: /^[A-Z0-9]+\/[A-Z0-9]+$/, message: '格式如：BTC/USDT' },
            ]}
            style={{ flex: 1 }}
          >
            <Input placeholder="BTC/USDT" style={{ textTransform: 'uppercase' }} />
          </Form.Item>
        </Space.Compact>

        <Space.Compact style={{ width: '100%', display: 'flex' }}>
          <Form.Item
            label="方向"
            name="direction"
            rules={[{ required: true, message: '请选择方向' }]}
            style={{ flex: 1, marginRight: 12 }}
          >
            <Select
              options={Object.entries(TRADE_DIRECTION_MAP).map(([k, v]) => ({
                value: k,
                label: (
                  <span style={{ color: v.color, fontWeight: 500 }}>
                    {v.text}
                  </span>
                ),
              }))}
            />
          </Form.Item>
          <Form.Item
            label="数量"
            name="amount"
            rules={[{ required: true, message: '请输入数量' }]}
            style={{ flex: 1, marginRight: 12 }}
          >
            <InputNumber
              style={{ width: '100%' }}
              min={0}
              step={0.0001}
              precision={6}
              placeholder="买入/卖出数量"
            />
          </Form.Item>
          <Form.Item
            label="价格"
            name="price"
            rules={[{ required: true, message: '请输入价格' }]}
            style={{ flex: 1 }}
          >
            <InputNumber
              style={{ width: '100%' }}
              min={0}
              step={0.01}
              precision={6}
              placeholder="成交单价"
            />
          </Form.Item>
        </Space.Compact>

        <Space.Compact style={{ width: '100%', display: 'flex' }}>
          <Form.Item label="手续费" name="fee" style={{ flex: 1, marginRight: 12 }}>
            <InputNumber
              style={{ width: '100%' }}
              min={0}
              step={0.000001}
              precision={8}
              placeholder="0.00"
            />
          </Form.Item>
          <Form.Item label="手续费币种" name="fee_currency" style={{ flex: 1, marginRight: 12 }}>
            <Input placeholder="USDT" style={{ textTransform: 'uppercase' }} />
          </Form.Item>
          <Form.Item
            label="交易时间"
            name="trade_time"
            rules={[{ required: true, message: '请选择时间' }]}
            style={{ flex: 1 }}
          >
            <DatePicker showTime style={{ width: '100%' }} format="YYYY-MM-DD HH:mm:ss" />
          </Form.Item>
        </Space.Compact>

        <Form.Item label="标签" name="tag_ids">
          <Select
            mode="multiple"
            placeholder="选择或新增标签"
            allowClear
            options={(tagsData || []).map((t: TradeTag) => ({
              value: t.id,
              label: (
                <span>
                  <Tag color={t.color} style={{ marginInlineEnd: 0 }}>
                    {t.name}
                  </Tag>
                </span>
              ),
            }))}
            dropdownRender={tagDropdownRender as any}
            optionLabelProp="label"
            maxTagCount="responsive"
          />
        </Form.Item>

        <Form.Item label="备注" name="remark">
          <Input.TextArea rows={2} placeholder="可选" maxLength={200} showCount />
        </Form.Item>
      </CrudModal>

      {/* 批量导入弹窗 */}
      <Modal
        title={
          <Space>
            <ImportOutlined />
            批量导入交易记录
          </Space>
        }
        open={importModalOpen}
        onCancel={() => setImportModalOpen(false)}
        footer={[
          <Button key="close" onClick={() => setImportModalOpen(false)}>
            {importResult ? '关闭' : '取消'}
          </Button>,
        ]}
        width={640}
        destroyOnClose
      >
        {!importResult ? (
          <>
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message="支持 CSV / Excel 文件，文件大小不超过 10MB"
              description="列顺序：币种、方向（buy/sell）、数量、价格、手续费、交易时间（YYYY-MM-DD HH:mm:ss）、备注"
            />
            <Dragger
              accept=".csv,.xlsx,.xls"
              multiple={false}
              maxCount={1}
              showUploadList={false}
              beforeUpload={handleImportFile}
              style={{ padding: 20 }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">
                点击或拖拽文件到此处上传
              </p>
              <p className="ant-upload-hint">
                {importing ? '正在导入中，请稍候...' : '仅支持 CSV / Excel 格式'}
              </p>
            </Dragger>
            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <Button
                icon={<DownloadOutlined />}
                type="link"
                onClick={() => {
                  const content =
                    'symbol,direction,amount,price,fee,trade_time,remark\nBTC/USDT,buy,0.1,65000,6.5,2026-08-01 10:00:00,\n';
                  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = '交易记录导入模板.csv';
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                下载导入模板
              </Button>
            </div>
            {importing && (
              <div style={{ marginTop: 16 }}>
                <Result
                  status="info"
                  icon={<div style={{ fontSize: 48 }}>⏳</div>}
                  title="导入中..."
                  subTitle="正在解析文件并批量导入，请稍候"
                />
              </div>
            )}
          </>
        ) : (
          <Result
            status={importResult.failed === 0 ? 'success' : 'warning'}
            title={importResult.failed === 0 ? '导入成功' : '导入部分失败'}
            subTitle={`共 ${importResult.total} 条，成功 ${importResult.success} 条，失败 ${importResult.failed} 条`}
            extra={
              importResult.errors.length > 0 ? (
                <Alert
                  type="error"
                  showIcon
                  style={{ textAlign: 'left' }}
                  message={`存在 ${importResult.errors.length} 条错误：`}
                  description={
                    <ul style={{ margin: 0, paddingLeft: 20 }}>
                      {importResult.errors.map((e, i) => (
                        <li key={i}>
                          第 {e.row} 行：{e.message}
                        </li>
                      ))}
                    </ul>
                  }
                />
              ) : null
            }
          />
        )}
      </Modal>
    </PageContainer>
  );
};

export default TradesPage;
