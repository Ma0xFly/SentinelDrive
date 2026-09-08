import { DownloadOutlined, PlusOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { PageContainer, ProTable } from '@ant-design/pro-components';
import { history, useModel } from '@umijs/max';
import { App, Button, Tag } from 'antd';
import React, { useRef } from 'react';
import ManualEntryCreateButton from '@/components/ManualEntryCreateButton';
import {
  attackSurfaceOptions,
  dateTimeLabel,
  intelligenceStatusOptions,
  intelligenceTypeOptions,
  labelFromOptions,
  optionsToValueEnum,
  riskLevelColor,
  riskLevelOptions,
  severityColor,
  severityOptions,
  vehicleComponentOptions,
} from '@/constants/labels';
import { exportIntelligenceCsv } from '@/services/exports';
import { listIntelligence } from '@/services/intelligence';
import { saveDownload } from '@/utils/download';

const PAGE_SIZE = 20;

const IntelligenceListPage: React.FC = () => {
  const actionRef = useRef<ActionType | undefined>(undefined);
  const { message } = App.useApp();
  const { initialState } = useModel('@@initialState');
  const isAuthenticated = !!initialState?.currentUser;
  const canIngest = !!initialState?.currentUser?.is_admin;

  const handleExportCsv = async () => {
    try {
      const result = await exportIntelligenceCsv();
      saveDownload(result);
      message.success('威胁情报 CSV 导出已开始下载');
    } catch {
      message.error('导出失败，请稍后重试。');
    }
  };

  const columns: ProColumns<API.IntelligenceListItem>[] = [
    {
      title: '标题',
      dataIndex: 'title',
      width: 300,
      ellipsis: true,
      fixed: 'left',
      render: (_, record) => (
        <a onClick={() => history.push(`/intelligence/${record.id}`)}>
          {record.title}
        </a>
      ),
    },
    {
      title: 'CVE',
      dataIndex: 'cve_id',
      width: 130,
      renderText: (value) => value || '-',
    },
    {
      title: '类型',
      dataIndex: 'intelligence_type',
      width: 90,
      valueType: 'select',
      valueEnum: optionsToValueEnum(intelligenceTypeOptions),
      render: (_, record) =>
        labelFromOptions(intelligenceTypeOptions, record.intelligence_type),
    },
    {
      title: '严重度',
      dataIndex: 'severity',
      width: 90,
      valueType: 'select',
      valueEnum: optionsToValueEnum(severityOptions),
      render: (_, record) => (
        <Tag color={severityColor[record.severity]}>
          {labelFromOptions(severityOptions, record.severity)}
        </Tag>
      ),
    },
    {
      title: '风险分',
      dataIndex: 'risk_score',
      width: 80,
      search: false,
      renderText: (value) =>
        value === null || value === undefined ? '-' : value,
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
      title: '厂商',
      dataIndex: 'vendor',
      hideInTable: true,
    },
    {
      title: '产品',
      dataIndex: 'product',
      hideInTable: true,
    },
    {
      title: '标签',
      dataIndex: 'tag',
      hideInTable: true,
    },
    {
      title: '来源',
      dataIndex: 'source',
      hideInTable: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      valueType: 'select',
      valueEnum: optionsToValueEnum(intelligenceStatusOptions),
      hideInTable: true,
    },
    {
      title: '厂商 / 产品',
      search: false,
      width: 170,
      ellipsis: true,
      render: (_, record) => {
        const parts = [record.affected_vendor, record.affected_product].filter(
          Boolean,
        );
        return parts.length > 0 ? parts.join(' / ') : '-';
      },
    },
    {
      title: '组件',
      dataIndex: 'vehicle_component',
      width: 100,
      valueType: 'select',
      valueEnum: optionsToValueEnum(vehicleComponentOptions),
      render: (_, record) =>
        labelFromOptions(vehicleComponentOptions, record.vehicle_component),
    },
    {
      title: '攻击面',
      dataIndex: 'attack_surface',
      width: 100,
      valueType: 'select',
      valueEnum: optionsToValueEnum(attackSurfaceOptions),
      hideInTable: true,
    },
    {
      title: '关联告警',
      dataIndex: 'related_alert_count',
      width: 90,
      search: false,
      renderText: (value) => (value > 0 ? value : '-'),
    },
    {
      title: '首次发现',
      dataIndex: 'first_seen_at',
      width: 150,
      search: false,
      renderText: (value) => dateTimeLabel(value),
    },
    {
      title: '最近更新',
      dataIndex: 'last_seen_at',
      width: 150,
      search: false,
      renderText: (value) => dateTimeLabel(value),
    },
    {
      title: '排序',
      dataIndex: 'sort',
      valueType: 'select',
      initialValue: 'recent',
      hideInTable: true,
      valueEnum: {
        recent: { text: '最近更新' },
        first_seen: { text: '首次发现' },
        risk_score: { text: '风险分' },
        severity: { text: '严重度' },
      },
    },
  ];

  return (
    <PageContainer title="威胁情报" subTitle="检索已归一化入库的车联网威胁情报">
      <ProTable<API.IntelligenceListItem>
        headerTitle="情报列表"
        actionRef={actionRef}
        rowKey="id"
        scroll={{ x: 1400 }}
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        request={async (params) => {
          const {
            current = 1,
            pageSize = PAGE_SIZE,
            vendor,
            product,
            tag,
            source,
            sort,
            ...rest
          } = params;
          const query: API.IntelligenceListParams = {
            page: current,
            limit: pageSize,
            vendor: vendor || undefined,
            product: product || undefined,
            tag: tag || undefined,
            source: source || undefined,
            sort: (sort as API.IntelligenceListParams['sort']) || 'recent',
            ...rest,
          };
          const page = await listIntelligence(query);
          return { data: page.items, success: true, total: page.total };
        }}
        pagination={{ defaultPageSize: PAGE_SIZE, showSizeChanger: true }}
        columns={columns}
        toolBarRender={() => [
          ...(isAuthenticated
            ? [
                <Button
                  key="export"
                  icon={<DownloadOutlined />}
                  onClick={handleExportCsv}
                >
                  导出 CSV
                </Button>,
              ]
            : []),
          ...(canIngest
            ? [
                <ManualEntryCreateButton
                  key="create"
                  type="primary"
                  icon={<PlusOutlined />}
                  onSuccess={() => actionRef.current?.reload()}
                />,
              ]
            : []),
        ]}
      />
    </PageContainer>
  );
};

export default IntelligenceListPage;
