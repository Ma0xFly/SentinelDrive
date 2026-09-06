import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { PageContainer, ProTable } from '@ant-design/pro-components';
import { history } from '@umijs/max';
import {
  App,
  Button,
  Descriptions,
  Drawer,
  Form,
  Input,
  Select,
  Space,
  Spin,
  Tag,
} from 'antd';
import React, { useRef, useState } from 'react';
import {
  alertStatusColor,
  alertStatusOptions,
  dateTimeLabel,
  labelFromOptions,
  optionsToValueEnum,
  riskLevelColor,
  riskLevelOptions,
  severityColor,
  severityOptions,
} from '@/constants/labels';
import { getAlert, listAlerts, updateAlertStatus } from '@/services/alerts';

const PAGE_SIZE = 20;

interface StatusFormValues {
  status: API.AlertStatus;
  notes?: string;
}

/**
 * 告警工作台：列表筛选、详情查看与状态流转。
 */
const AlertsPage: React.FC = () => {
  const actionRef = useRef<ActionType | undefined>(undefined);
  const { message } = App.useApp();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detail, setDetail] = useState<API.AlertDetail>();
  const [detailLoading, setDetailLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<StatusFormValues>();

  const openDetail = async (record: API.Alert) => {
    setDrawerOpen(true);
    setDetailLoading(true);
    form.resetFields();
    try {
      const result = await getAlert(record.id, { skipErrorHandler: true });
      setDetail(result);
      form.setFieldsValue({ status: result.status, notes: result.notes ?? '' });
    } catch {
      message.error('告警详情加载失败，请稍后重试。');
      setDrawerOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleStatusSubmit = async (values: StatusFormValues) => {
    if (!detail) {
      return;
    }
    setSubmitting(true);
    try {
      const notesTouched = form.isFieldTouched('notes');
      const payload: API.AlertStatusUpdateParams = { status: values.status };
      if (notesTouched) {
        payload.notes = values.notes ? values.notes : null;
      }
      const updated = await updateAlertStatus(detail.id, payload);
      setDetail(updated);
      form.setFieldsValue({
        status: updated.status,
        notes: updated.notes ?? '',
      });
      message.success('告警状态已更新');
      actionRef.current?.reload();
    } catch {
      message.error('状态更新失败，请稍后重试。');
    } finally {
      setSubmitting(false);
    }
  };

  const columns: ProColumns<API.Alert>[] = [
    {
      title: '告警标题',
      dataIndex: 'title',
      width: 320,
      ellipsis: true,
      render: (_, record) => (
        <a onClick={() => openDetail(record)}>{record.title}</a>
      ),
    },
    {
      title: '触发规则',
      dataIndex: 'triggering_rule',
      width: 180,
      ellipsis: true,
      copyable: true,
    },
    {
      title: '风险等级',
      dataIndex: 'risk_level',
      width: 100,
      valueType: 'select',
      valueEnum: optionsToValueEnum(riskLevelOptions),
      render: (_, record) => (
        <Tag color={riskLevelColor[record.risk_level]}>
          {labelFromOptions(riskLevelOptions, record.risk_level)}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      valueType: 'select',
      valueEnum: optionsToValueEnum(alertStatusOptions),
      render: (_, record) => (
        <Tag color={alertStatusColor[record.status]}>
          {labelFromOptions(alertStatusOptions, record.status)}
        </Tag>
      ),
    },
    {
      title: '触发时间',
      dataIndex: 'triggered_at',
      width: 160,
      search: false,
      renderText: (value) => dateTimeLabel(value),
    },
    {
      title: '操作',
      valueType: 'option',
      width: 90,
      render: (_, record) => [
        <a key="detail" onClick={() => openDetail(record)}>
          处置
        </a>,
      ],
    },
  ];

  const detailItems = detail
    ? [
        {
          key: 'risk',
          label: '风险等级',
          children: (
            <Tag color={riskLevelColor[detail.risk_level]}>
              {labelFromOptions(riskLevelOptions, detail.risk_level)}
            </Tag>
          ),
        },
        {
          key: 'status',
          label: '当前状态',
          children: (
            <Tag color={alertStatusColor[detail.status]}>
              {labelFromOptions(alertStatusOptions, detail.status)}
            </Tag>
          ),
        },
        {
          key: 'rule',
          label: '触发规则',
          span: 2,
          children: (
            <span style={{ wordBreak: 'break-all' }}>
              {detail.triggering_rule}
            </span>
          ),
        },
        {
          key: 'triggered',
          label: '触发时间',
          children: dateTimeLabel(detail.triggered_at),
        },
        {
          key: 'updated',
          label: '最近更新',
          children: dateTimeLabel(detail.updated_at),
        },
        {
          key: 'notes',
          label: '备注',
          span: 2,
          children: (
            <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {detail.notes || '-'}
            </span>
          ),
        },
      ]
    : [];

  return (
    <PageContainer title="告警" subTitle="查看与处置由告警规则触发的威胁告警">
      <ProTable<API.Alert>
        headerTitle="告警列表"
        actionRef={actionRef}
        rowKey="id"
        scroll={{ x: 1000 }}
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        request={async (params) => {
          const { current = 1, pageSize = PAGE_SIZE, ...rest } = params;
          const page = await listAlerts({
            page: current,
            limit: pageSize,
            ...rest,
          });
          return { data: page.items, success: true, total: page.total };
        }}
        pagination={{ defaultPageSize: PAGE_SIZE, showSizeChanger: true }}
        columns={columns}
        options={false}
      />

      <Drawer
        title="告警详情"
        width={560}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        destroyOnHidden
      >
        {detailLoading || !detail ? (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin />
          </div>
        ) : (
          <Space direction="vertical" size={24} style={{ width: '100%' }}>
            <Descriptions column={2} size="small" items={detailItems} />

            {detail.intelligence && (
              <Space direction="vertical" size={4}>
                <Space size={8} wrap>
                  <Tag color={severityColor[detail.intelligence.severity]}>
                    {labelFromOptions(
                      severityOptions,
                      detail.intelligence.severity,
                    )}
                  </Tag>
                  {detail.intelligence.cve_id && (
                    <Tag>{detail.intelligence.cve_id}</Tag>
                  )}
                </Space>
                <a
                  onClick={() => {
                    setDrawerOpen(false);
                    history.push(`/intelligence/${detail.intelligence?.id}`);
                  }}
                >
                  打开关联情报：{detail.intelligence.title}
                </a>
              </Space>
            )}

            <Form form={form} layout="vertical" onFinish={handleStatusSubmit}>
              <Form.Item
                name="status"
                label="流转到状态"
                rules={[{ required: true, message: '请选择目标状态' }]}
              >
                <Select
                  options={alertStatusOptions.map(([value, label]) => ({
                    value,
                    label,
                  }))}
                />
              </Form.Item>
              <Form.Item
                name="notes"
                label="备注"
                tooltip="未编辑备注时保留原备注；清空并提交将清除备注。"
              >
                <Input.TextArea
                  rows={4}
                  placeholder="记录处置说明（不得包含密钥等敏感信息）"
                />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={submitting}>
                更新状态
              </Button>
            </Form>
          </Space>
        )}
      </Drawer>
    </PageContainer>
  );
};

export default AlertsPage;
