import { useEffect, useState } from 'react';
import { Modal, Form, Spin } from 'antd';
import type { ReactNode } from 'react';
import type { FormProps, ModalProps } from 'antd';

export type CrudModalMode = 'create' | 'edit' | 'view';

export interface CrudModalProps<T = any> {
  /** 弹窗开关 */
  open: boolean;
  /** 模式 */
  mode: CrudModalMode;
  /** 标题，不传则根据模式自动生成 */
  title?: string;
  /** 实体名称（用于自动生成标题） */
  entityName?: string;
  /** 初始值 */
  initialValues?: Partial<T>;
  /** 表单字段（children） */
  children: ReactNode;
  /** 确认回调，返回 Promise 自动处理 loading */
  onOk: (values: T) => Promise<void> | void;
  /** 取消回调 */
  onCancel: () => void;
  /** Form props */
  formProps?: Omit<FormProps, 'form' | 'initialValues' | 'onFinish'>;
  /** Modal props */
  modalProps?: Omit<ModalProps, 'open' | 'title' | 'onOk' | 'onCancel' | 'confirmLoading' | 'okText' | 'cancelText'>;
  /** 只读模式 */
  readOnly?: boolean;
  /** 自定义 OK 按钮文本 */
  okText?: string;
}

const CrudModal = <T extends Record<string, any>>({
  open,
  mode,
  title,
  entityName = '记录',
  initialValues,
  children,
  onOk,
  onCancel,
  formProps,
  modalProps,
  readOnly,
  okText,
}: CrudModalProps<T>) => {
  const [form] = Form.useForm<T>();
  const [submitting, setSubmitting] = useState(false);

  const isReadOnly = readOnly || mode === 'view';

  const getTitle = () => {
    if (title) return title;
    const map: Record<CrudModalMode, string> = {
      create: `新增${entityName}`,
      edit: `编辑${entityName}`,
      view: `查看${entityName}`,
    };
    return map[mode];
  };

  // 每次打开时重置表单并填充初始值
  useEffect(() => {
    if (open) {
      form.resetFields();
      if (initialValues) {
        form.setFieldsValue(initialValues as any);
      }
    }
  }, [open, initialValues]);

  const handleOk = async () => {
    if (isReadOnly) {
      onCancel();
      return;
    }
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      await onOk(values as T);
    } catch (err: any) {
      if (err?.errorFields) return;
      throw err;
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={getTitle()}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={submitting}
      okText={okText || (isReadOnly ? '关闭' : '确定')}
      cancelText="取消"
      okButtonProps={isReadOnly ? { style: { display: 'none' } } : undefined}
      destroyOnHidden
      maskClosable={false}
      width={640}
      {...modalProps}
    >
      <Spin spinning={submitting}>
        <Form
          form={form}
          layout="vertical"
          disabled={isReadOnly}
          initialValues={initialValues as any}
          {...formProps}
          style={{ maxHeight: '60vh', overflowY: 'auto', paddingRight: 8 }}
        >
          {children}
        </Form>
      </Spin>
    </Modal>
  );
};

export default CrudModal;
