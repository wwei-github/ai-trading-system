import { useEffect } from 'react';
import { Form, Button, Row, Col, Space } from 'antd';
import type { FormProps, ColProps } from 'antd';
import type { ReactNode } from 'react';

export interface SearchField {
  /** 字段 name */
  name: string;
  /** label 标签 */
  label: string;
  /** 表单控件 */
  element: ReactNode;
  /** 占位符 */
  placeholder?: string;
  /** 占用栅格数，默认 6 */
  span?: number;
  /** 是否必填 */
  required?: boolean;
}

export interface SearchFormProps<V = any> {
  /** 搜索字段配置 */
  fields: SearchField[];
  /** 搜索提交回调 */
  onSearch: (values: V) => void;
  /** 重置回调 */
  onReset?: () => void;
  /** 初始值 */
  initialValues?: Partial<V>;
  /** 布局：horizontal（默认，一行多列）或 vertical */
  layout?: FormProps['layout'];
  /** 列数，默认一行4列 */
  columns?: 2 | 3 | 4;
  /** 自定义按钮 */
  extraButtons?: ReactNode;
  /** Form props 扩展 */
  formProps?: Omit<FormProps, 'form' | 'layout' | 'initialValues' | 'onFinish'>;
  /** 是否显示查询/重置按钮 */
  showActions?: boolean;
}

const DEFAULT_COL_SPAN: Record<number, ColProps['span']> = {
  2: 12,
  3: 8,
  4: 6,
};

const SearchForm = <V extends Record<string, any>>({
  fields,
  onSearch,
  onReset,
  initialValues,
  layout = 'horizontal',
  columns = 4,
  extraButtons,
  formProps,
  showActions = true,
}: SearchFormProps<V>) => {
  const [form] = Form.useForm<V>();

  const colSpan = DEFAULT_COL_SPAN[columns];

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue(initialValues);
    }
  }, [initialValues]);

  const handleSearch = async () => {
    const values = form.getFieldsValue(true);
    onSearch(values as V);
  };

  const handleReset = () => {
    form.resetFields();
    const values = form.getFieldsValue(true);
    onSearch(values as V);
    onReset?.();
  };

  const { labelCol, wrapperCol } = layout === 'horizontal'
    ? { labelCol: { flex: '100px' }, wrapperCol: { flex: 1 } }
    : {};

  return (
    <Form
      form={form}
      layout={layout}
      initialValues={initialValues}
      labelCol={labelCol}
      wrapperCol={wrapperCol}
      {...formProps}
    >
      <Row gutter={16} style={{ alignItems: 'flex-end' }}>
        {fields.map((field) => (
          <Col key={field.name} span={field.span ?? colSpan} style={{ marginBottom: 12 }}>
            <Form.Item
              label={field.label}
              name={field.name}
              rules={field.required ? [{ required: true, message: `请输入${field.label}` }] : undefined}
              style={{ marginBottom: 0 }}
            >
              {field.element}
            </Form.Item>
          </Col>
        ))}
        {showActions && (
          <Col span={colSpan} style={{ marginBottom: 12 }}>
            <Space>
              <Button type="primary" onClick={handleSearch}>
                查询
              </Button>
              <Button onClick={handleReset}>重置</Button>
              {extraButtons}
            </Space>
          </Col>
        )}
      </Row>
    </Form>
  );
};

export default SearchForm;
