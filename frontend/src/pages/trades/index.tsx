import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  DatePicker,
  Form,
  Input,
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
} from 'antd';
import {
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
  EmptyState,
} from '@/components/Common';
import { tradeApi, accountApi } from '@/api';
import type {
  Trade,
  TradeFormData,
  TradeListParams,
  TradeDirection,
  BatchImportResult,
  Account,
} from '@/types';
import { TRADE_DIRECTION_MAP } from '@/types/trades';
import { EXCHANGE_OPTIONS } from '@/types/accounts';

const { RangePicker } = DatePicker;
const { Dragger } = Upload;

// 交易状态展示映射（未知状态回退为原值）
const TRADE_STATUS_MAP: Record<string, { text: string; color: string }> = {
  filled: { text: '已成交', color: 'green' },
  partial: { text: '部分成交', color: 'blue' },
  pending: { text: '待成交', color: 'gold' },
  cancelled: { text: '已取消', color: 'default' },
  rejected: { text: '已拒绝', color: 'red' },
};

type SearchValues = Partial<TradeListParams> & { time_range?: [dayjs.Dayjs, dayjs.Dayjs] };

const TradesPage = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useState<SearchValues>({
    page: 1,
    page_size: 15,
  });
  const [tagsModalOpen, setTagsModalOpen] = useState(false);
  const [currentRecord, setCurrentRecord] = useState<Trade | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importAccountId, setImportAccountId] = useState<string | undefined>();
  const [importResult, setImportResult] = useState<BatchImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);

  // ========== 查询列表 ==========
  const actualQueryParams: TradeListParams = useMemo(() => {
    const { time_range, ...rest } = searchParams;
    return {
      ...rest,
      start_date: time_range?.[0]?.format('YYYY-MM-DD'),
      end_date: time_range?.[1]?.format('YYYY-MM-DD'),
    };
  }, [searchParams]);

  const { data, isLoading } = useQuery({
    queryKey: ['trades', 'list', actualQueryParams],
    queryFn: () => tradeApi.getList(actualQueryParams),
  });

  // 账号列表（用于导入目标选择与表格展示，getList 返回 Account[]）
  const { data: accountsData } = useQuery({
    queryKey: ['accounts', 'select'],
    queryFn: () => accountApi.getList(),
  });

  const accountOptions = useMemo(
    () =>
      (accountsData || []).map((a) => ({
        value: a.id,
        label: a.label,
      })),
    [accountsData],
  );

  const accountMap = useMemo(() => {
    const m = new Map<string, Account>();
    (accountsData || []).forEach((a) => m.set(a.id, a));
    return m;
  }, [accountsData]);

  // ========== 更新标签/备注 ==========
  const updateTagsMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { tags?: string[]; note?: string } }) =>
      tradeApi.updateTags(id, data),
    onSuccess: () => {
      message.success('更新成功');
      queryClient.invalidateQueries({ queryKey: ['trades'] });
      setTagsModalOpen(false);
    },
  });

  // ========== 导出 ==========
  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await tradeApi.exportTrades(actualQueryParams, 'csv');
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

  // ========== CSV 解析（客户端解析为 TradeFormData[]，再调用批量导入接口） ==========
  const parseCsvLine = (line: string): string[] => {
    const result: string[] = [];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"') {
          if (line[i + 1] === '"') {
            cur += '"';
            i++;
          } else {
            inQuotes = false;
          }
        } else {
          cur += ch;
        }
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ',') {
        result.push(cur);
        cur = '';
      } else {
        cur += ch;
      }
    }
    result.push(cur);
    return result;
  };

  const parseTradesCsv = (
    text: string,
    accountId: string,
    exchange: string,
  ): { trades: TradeFormData[]; errors: string[] } => {
    const errors: string[] = [];
    const lines = text
      .replace(/\r\n/g, '\n')
      .split('\n')
      .filter((l) => l.trim() !== '');
    if (lines.length === 0) {
      return { trades: [], errors: ['文件为空'] };
    }
    const header = parseCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
    const required = ['symbol', 'side', 'price', 'quantity', 'executed_at'];
    const missing = required.filter((f) => !header.includes(f));
    if (missing.length > 0) {
      return { trades: [], errors: [`表头缺少必需列：${missing.join(', ')}`] };
    }
    const trades: TradeFormData[] = [];
    for (let i = 1; i < lines.length; i++) {
      const cells = parseCsvLine(lines[i]);
      const row: Partial<Record<string, string>> = {};
      header.forEach((h, j) => {
        row[h] = (cells[j] ?? '').trim();
      });
      const price = Number(row.price);
      const quantity = Number(row.quantity);
      if (
        !row.symbol ||
        !row.side ||
        !row.executed_at ||
        Number.isNaN(price) ||
        Number.isNaN(quantity)
      ) {
        errors.push(`第 ${i + 1} 行：必需字段缺失或无效`);
        continue;
      }
      const item: TradeFormData = {
        account_id: accountId,
        exchange,
        symbol: row.symbol,
        side: row.side as TradeDirection,
        price,
        quantity,
        executed_at: row.executed_at,
      };
      if (row.market_type) item.market_type = row.market_type;
      if (row.order_type) item.order_type = row.order_type;
      if (row.fee !== undefined && row.fee !== '') item.fee = Number(row.fee);
      if (row.fee_currency) item.fee_currency = row.fee_currency;
      if (row.leverage !== undefined && row.leverage !== '') item.leverage = Number(row.leverage);
      if (row.status) item.status = row.status;
      if (row.strategy_id) item.strategy_id = row.strategy_id;
      if (row.tags) {
        item.tags = row.tags
          .split(/[;|]/)
          .map((t) => t.trim())
          .filter(Boolean);
      }
      if (row.note) item.note = row.note;
      if (row.exchange_order_id) item.exchange_order_id = row.exchange_order_id;
      trades.push(item);
    }
    return { trades, errors };
  };

  // ========== 导入 ==========
  const handleImportFile = async (file: File) => {
    if (!importAccountId) {
      message.warning('请先选择导入的目标账号');
      return false;
    }
    const account = accountMap.get(importAccountId);
    if (!account) {
      message.warning('所选账号不存在');
      return false;
    }
    setImporting(true);
    setImportResult(null);
    try {
      const text = await file.text();
      const { trades, errors: parseErrors } = parseTradesCsv(
        text,
        importAccountId,
        account.exchange,
      );
      if (trades.length === 0) {
        setImportResult({
          total: parseErrors.length,
          imported: 0,
          skipped: parseErrors.length,
          errors: parseErrors,
        });
        return false;
      }
      const result = await tradeApi.batchImport(importAccountId, trades);
      const merged: BatchImportResult = {
        total: result.total,
        imported: result.imported,
        skipped: result.skipped + parseErrors.length,
        errors: [...parseErrors, ...result.errors],
      };
      setImportResult(merged);
      if (merged.skipped === 0) {
        message.success(`导入成功：${merged.imported} 条`);
      } else {
        message.warning(`导入完成：成功 ${merged.imported} 条，跳过 ${merged.skipped} 条`);
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
        name: 'exchange',
        label: '交易所',
        element: (
          <Select
            allowClear
            placeholder="全部"
            options={EXCHANGE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
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
        name: 'side',
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
        name: 'status',
        label: '状态',
        element: (
          <Select
            allowClear
            placeholder="全部"
            options={Object.entries(TRADE_STATUS_MAP).map(([k, v]) => ({
              value: k,
              label: v.text,
            }))}
          />
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
    ],
    [],
  );

  // ========== 表格列 ==========
  const columns = useMemo(
    () => [
      {
        title: '成交时间',
        dataIndex: 'executed_at',
        key: 'executed_at',
        width: 170,
        sorter: (a: Trade, b: Trade) => a.executed_at.localeCompare(b.executed_at),
        render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
      },
      {
        title: '账号',
        dataIndex: 'account_id',
        key: 'account_id',
        width: 140,
        render: (v: string) => (
          <Tag color="geekblue">{accountMap.get(v)?.label || v}</Tag>
        ),
      },
      {
        title: '交易所',
        dataIndex: 'exchange',
        key: 'exchange',
        width: 100,
        render: (v: string) => {
          const opt = EXCHANGE_OPTIONS.find((o) => o.value === v);
          return opt ? opt.label : v;
        },
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
        dataIndex: 'side',
        key: 'side',
        width: 80,
        render: (v: TradeDirection) => (
          <span style={{ color: TRADE_DIRECTION_MAP[v]?.color, fontWeight: 600 }}>
            {TRADE_DIRECTION_MAP[v]?.text || v}
          </span>
        ),
      },
      {
        title: '数量',
        dataIndex: 'quantity',
        key: 'quantity',
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
        key: 'total',
        width: 150,
        align: 'right' as const,
        render: (_: unknown, rec: Trade) => (
          <AmountText value={rec.price * rec.quantity} suffix=" USDT" fontWeight={600} precision={2} />
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
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (v: string) => {
          const m = TRADE_STATUS_MAP[v];
          return <Tag color={m?.color || 'default'}>{m?.text || v || '-'}</Tag>;
        },
      },
      {
        title: '标签',
        dataIndex: 'tags',
        key: 'tags',
        width: 180,
        render: (tags?: string[]) =>
          tags && tags.length > 0 ? (
            <Space size={[4, 4]} wrap>
              {tags.map((t, i) => (
                <Tag key={`${t}-${i}`} style={{ margin: 2 }}>
                  {t}
                </Tag>
              ))}
            </Space>
          ) : null,
      },
      {
        title: '备注',
        dataIndex: 'note',
        key: 'note',
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
        width: 110,
        fixed: 'right' as const,
        render: (_: unknown, record: Trade) => (
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setCurrentRecord(record);
              setTagsModalOpen(true);
            }}
          >
            标签/备注
          </Button>
        ),
      },
    ],
    [accountMap],
  );

  // ========== 标签/备注提交 ==========
  const handleTagsSubmit = async (values: { tags?: string[]; note?: string }) => {
    if (!currentRecord) return;
    await updateTagsMutation.mutateAsync({
      id: currentRecord.id,
      data: { tags: values.tags, note: values.note },
    });
  };

  const tagsInitialValues = useMemo(
    () => ({
      tags: currentRecord?.tags || [],
      note: currentRecord?.note || '',
    }),
    [currentRecord],
  );

  return (
    <PageContainer
      breadcrumbs={[{ title: '交易记录' }]}
      title="交易记录管理"
      description="交易记录查询、批量导入导出与标签/备注管理"
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
          <Button icon={<ExportOutlined />} onClick={handleExport} loading={exporting}>
            批量导出
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
          showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
          onChange: (page, pageSize) => {
            setSearchParams((prev) => ({ ...prev, page, page_size: pageSize }));
          },
        }}
        locale={{
          emptyText: <EmptyState description="暂无交易记录，可使用批量导入添加" />,
        }}
      />

      {/* 标签/备注编辑弹窗 */}
      <CrudModal<{ tags?: string[]; note?: string }>
        open={tagsModalOpen}
        mode="edit"
        title="编辑标签/备注"
        initialValues={tagsInitialValues}
        onOk={handleTagsSubmit}
        onCancel={() => setTagsModalOpen(false)}
        modalProps={{ width: 520 }}
      >
        <Form.Item label="标签" name="tags" tooltip="输入后回车添加标签">
          <Select mode="tags" placeholder="添加标签" allowClear maxTagCount="responsive" />
        </Form.Item>
        <Form.Item label="备注" name="note">
          <Input.TextArea rows={3} placeholder="可选" maxLength={500} showCount />
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
        destroyOnHidden
      >
        {!importResult ? (
          <>
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message="选择目标账号后上传 CSV 文件，文件大小不超过 10MB"
              description="列顺序（含表头）：symbol, side, quantity, price, fee, fee_currency, executed_at, note"
            />
            <Form.Item label="目标账号" required style={{ marginBottom: 16 }}>
              <Select
                placeholder="请选择导入的目标账号"
                options={accountOptions}
                value={importAccountId}
                onChange={setImportAccountId}
                showSearch
                optionFilterProp="label"
              />
            </Form.Item>
            <Dragger
              accept=".csv"
              multiple={false}
              maxCount={1}
              showUploadList={false}
              beforeUpload={handleImportFile}
              disabled={!importAccountId || importing}
              style={{ padding: 20 }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
              <p className="ant-upload-hint">
                {importing ? '正在导入中，请稍候...' : '仅支持 CSV 格式'}
              </p>
            </Dragger>
            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <Button
                icon={<DownloadOutlined />}
                type="link"
                onClick={() => {
                  const content =
                    'symbol,side,quantity,price,fee,fee_currency,executed_at,note\nBTC/USDT,buy,0.1,65000,6.5,USDT,2026-08-01 10:00:00,测试导入\n';
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
            status={importResult.skipped === 0 ? 'success' : 'warning'}
            title={importResult.skipped === 0 ? '导入成功' : '导入部分失败'}
            subTitle={`共 ${importResult.total} 条，成功 ${importResult.imported} 条，跳过 ${importResult.skipped} 条`}
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
                        <li key={i}>{e}</li>
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
