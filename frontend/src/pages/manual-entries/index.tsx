import { PlusOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { PageContainer, ProTable } from '@ant-design/pro-components';
import { App, Tag } from 'antd';
import React, { useRef } from 'react';
import ManualEntryCreateButton from '@/components/ManualEntryCreateButton';
import {
  dateTimeLabel,
  labelFromOptions,
  manualCategoryOptions,
  riskLevelColor,
  riskLevelOptions,
  severityColor,
  severityOptions,
} from '@/constants/labels';
import { listManualEntries } from '@/services/manualEntries';

/**
 * 手工录入工作台：登记漏洞、公告、事件、暴露面与研究线索。
 */
const ManualEntriesPage: React.FC = () => {
  const actionRef = useRef<ActionType | undefined>(undefined);
  const { message } = App.useApp();

  const columns: ProColumns<API.ManualEntry>[] = [
    {
      title: '标题',
      dataIndex: 'title',
      width: 280,
      ellipsis: true,
      fixed: 'left',
    },
    {
      title: '类别',
      dataIndex: 'category',
      width: 90,
      valueEnum: Object.fromEntries(
        manualCategoryOptions.map(([value, label]) => [value, { text: label }]),
      ),
      render: (_, record) =>
        labelFromOptions(manualCategoryOptions, record.category),
    },
    {
      title: '来源',
      dataIndex: 'source_name',
      width: 160,
      ellipsis: true,
      hideInTable: true,
      renderText: (value) => value || '-',
    },
    {
      title: '来源 URL',
      dataIndex: 'source_url',
      width: 220,
      ellipsis: true,
      hideInTable: true,
      render: (_, record) =>
        record.source_url ? (
          <a href={record.source_url} target="_blank" rel="noopener noreferrer">
            {record.source_url}
          </a>
        ) : (
          '-'
        ),
    },
    {
      title: 'CVE',
      dataIndex: 'cve_id',
      width: 130,
      renderText: (value) => value || '-',
    },
    {
      title: '严重度',
      dataIndex: 'severity',
      width: 90,
      valueEnum: Object.fromEntries(
        severityOptions.map(([value, label]) => [value, { text: label }]),
      ),
      render: (_, record) => (
        <Tag color={severityColor[record.severity]}>
          {labelFromOptions(severityOptions, record.severity)}
        </Tag>
      ),
    },
    {
      title: '风险等级',
      dataIndex: 'risk_level',
      width: 100,
      valueEnum: Object.fromEntries(
        riskLevelOptions.map(([value, label]) => [value, { text: label }]),
      ),
      render: (_, record) => (
        <Tag color={riskLevelColor[record.risk_level]}>
          {labelFromOptions(riskLevelOptions, record.risk_level)}
        </Tag>
      ),
    },
    {
      title: '厂商 / 产品',
      width: 170,
      ellipsis: true,
      search: false,
      render: (_, record) => {
        const parts = [record.affected_vendor, record.affected_product].filter(
          Boolean,
        );
        return parts.length > 0 ? parts.join(' / ') : '-';
      },
    },
    {
      title: '最近更新',
      dataIndex: 'last_seen_at',
      width: 160,
      search: false,
      renderText: (value) => dateTimeLabel(value),
    },
  ];

  return (
    <PageContainer
      title="手工录入"
      subTitle="手工登记安全情报，纳入统一归一化与评分流程"
      extra={[
        <ManualEntryCreateButton
          key="create"
          type="primary"
          icon={<PlusOutlined />}
          onSuccess={() => actionRef.current?.reload()}
        />,
      ]}
    >
      <ProTable<API.ManualEntry>
        headerTitle="录入记录"
        actionRef={actionRef}
        rowKey="id"
        scroll={{ x: 1200 }}
        search={false}
        options={false}
        request={async () => {
          try {
            const items = await listManualEntries();
            return { data: items, success: true, total: items.length };
          } catch {
            message.error('手工录入列表加载失败，请稍后重试。');
            return { data: [], success: false, total: 0 };
          }
        }}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        columns={columns}
      />
    </PageContainer>
  );
};

export default ManualEntriesPage;
