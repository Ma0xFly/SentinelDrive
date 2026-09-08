import { CaretRightOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ActionType, ProColumns } from '@ant-design/pro-components';
import { PageContainer, ProTable } from '@ant-design/pro-components';
import { useModel } from '@umijs/max';
import {
  App,
  Button,
  Drawer,
  Popconfirm,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import React, { useRef, useState } from 'react';
import {
  dateTimeLabel,
  jobStatusColor,
  jobStatusOptions,
  labelFromOptions,
  optionsToValueEnum,
  sourceStatusColor,
  sourceStatusOptions,
  sourceTypeOptions,
} from '@/constants/labels';
import {
  listJobLogs,
  listSources,
  triggerPipeline,
  updateSourceStatus,
} from '@/services/sources';

const PAGE_SIZE = 20;
const { Text } = Typography;

/**
 * 数据源管理：采集源状态、任务日志与同步控制。
 */
const SourcesPage: React.FC = () => {
  const actionRef = useRef<ActionType | undefined>(undefined);
  const { message, modal } = App.useApp();
  const { initialState } = useModel('@@initialState');
  const isAuthenticated = !!initialState?.currentUser;
  const [logsOpen, setLogsOpen] = useState(false);
  const [logsSource, setLogsSource] = useState<API.Source | undefined>(
    undefined,
  );
  const [logs, setLogs] = useState<API.JobLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [togglingId, setTogglingId] = useState<string>();

  const openLogs = async (record: API.Source) => {
    setLogsSource(record);
    setLogsOpen(true);
    setLogsLoading(true);
    try {
      const page = await listJobLogs({
        source_id: record.id,
        limit: 50,
        sort: 'recent',
      });
      setLogs(page.items);
    } catch {
      message.error('任务日志加载失败，请稍后重试。');
      setLogs([]);
    } finally {
      setLogsLoading(false);
    }
  };

  const handleToggle = async (record: API.Source) => {
    const targetStatus = record.status === 'enabled' ? 'disabled' : 'enabled';
    setTogglingId(record.id);
    try {
      await updateSourceStatus(record.id, {
        status: targetStatus,
        reason: targetStatus === 'disabled' ? '运营人员在数据源页面停用' : null,
      });
      message.success(
        targetStatus === 'enabled'
          ? `数据源「${record.name}」已启用`
          : `数据源「${record.name}」已停用`,
      );
      actionRef.current?.reload();
    } catch {
      message.error('数据源状态更新失败，请稍后重试。');
    } finally {
      setTogglingId(undefined);
    }
  };

  const handleTriggerPipeline = () => {
    modal.confirm({
      title: '手动触发采集管道',
      content:
        '将对所有启用的数据源执行一次采集、归一化、评分与告警评估，确认执行？',
      okText: '触发同步',
      cancelText: '取消',
      onOk: async () => {
        setTriggering(true);
        try {
          const result = await triggerPipeline();
          message.success(
            `采集管道任务已提交（${result.message || result.status}）`,
          );
          actionRef.current?.reload();
        } catch {
          message.error('触发失败，请稍后重试。');
        } finally {
          setTriggering(false);
        }
      },
    });
  };

  const columns: ProColumns<API.Source>[] = [
    {
      title: '数据源',
      dataIndex: 'name',
      width: 200,
      ellipsis: true,
      fixed: 'left',
    },
    {
      title: '类型',
      dataIndex: 'source_type',
      width: 90,
      valueType: 'select',
      valueEnum: optionsToValueEnum(sourceTypeOptions),
      render: (_, record) =>
        labelFromOptions(sourceTypeOptions, record.source_type),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      valueType: 'select',
      valueEnum: optionsToValueEnum(sourceStatusOptions),
      render: (_, record) => (
        <Tag color={sourceStatusColor[record.status]}>
          {labelFromOptions(sourceStatusOptions, record.status)}
        </Tag>
      ),
    },
    {
      title: '关键字',
      dataIndex: 'q',
      hideInTable: true,
    },
    {
      title: '最近成功同步',
      dataIndex: 'last_success_at',
      width: 160,
      search: false,
      renderText: (value) => dateTimeLabel(value),
    },
    {
      title: '失败次数',
      dataIndex: 'failure_count',
      width: 90,
      search: false,
      align: 'right',
      renderText: (value) =>
        value > 0 ? <Text type="danger">{value}</Text> : 0,
    },
    {
      title: '最近错误',
      dataIndex: 'last_error_message',
      width: 220,
      search: false,
      ellipsis: true,
      renderText: (value) => value || '-',
    },
    {
      title: '同步游标',
      dataIndex: 'sync_cursor',
      search: false,
      hideInTable: true,
    },
    ...(isAuthenticated
      ? [
          {
            title: '操作',
            valueType: 'option' as const,
            width: 200,
            fixed: 'right' as const,
            render: (_: unknown, record: API.Source) => [
              <a key="logs" onClick={() => openLogs(record)}>
                任务日志
              </a>,
              <Popconfirm
                key="toggle"
                title={
                  record.status === 'enabled'
                    ? '确认停用该数据源？'
                    : '确认启用该数据源？'
                }
                description={
                  record.status === 'enabled'
                    ? '停用后不再执行自动采集。'
                    : '启用后将恢复自动采集。'
                }
                okText="确认"
                cancelText="取消"
                onConfirm={() => handleToggle(record)}
              >
                <a
                  onClick={() => {
                    if (togglingId !== record.id) {
                      void 0;
                    }
                  }}
                  style={
                    togglingId === record.id
                      ? { color: 'rgba(0,0,0,0.25)', cursor: 'not-allowed' }
                      : undefined
                  }
                >
                  {record.status === 'enabled' ? '停用' : '启用'}
                </a>
              </Popconfirm>,
            ],
          },
        ]
      : []),
  ];

  return (
    <PageContainer
      title="数据源"
      subTitle="查看采集数据源运行状况并控制采集管道"
      extra={[
        <Tooltip key="refresh-tip" title="刷新列表">
          <Button
            icon={<ReloadOutlined />}
            onClick={() => actionRef.current?.reload()}
          />
        </Tooltip>,
        ...(isAuthenticated
          ? [
              <Button
                key="trigger"
                type="primary"
                icon={<CaretRightOutlined />}
                loading={triggering}
                onClick={handleTriggerPipeline}
              >
                手动触发同步
              </Button>,
            ]
          : []),
      ]}
    >
      <ProTable<API.Source>
        headerTitle="采集数据源"
        actionRef={actionRef}
        rowKey="id"
        scroll={{ x: 1100 }}
        search={{ labelWidth: 'auto', defaultCollapsed: false }}
        request={async (params) => {
          const { current = 1, pageSize = PAGE_SIZE, ...rest } = params;
          const page = await listSources({
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
        title={`任务日志：${logsSource?.name || ''}`}
        width={720}
        open={logsOpen}
        onClose={() => setLogsOpen(false)}
        destroyOnHidden
      >
        {logsLoading ? (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin />
          </div>
        ) : (
          <Table
            rowKey="id"
            size="small"
            pagination={{ pageSize: 10, showSizeChanger: false }}
            dataSource={logs}
            columns={[
              {
                title: '状态',
                dataIndex: 'status',
                width: 90,
                filters: jobStatusOptions.map(([value, label]) => ({
                  text: label,
                  value,
                })),
                onFilter: (value, record) => record.status === value,
                render: (value) => (
                  <Tag color={jobStatusColor[value]}>
                    {labelFromOptions(jobStatusOptions, value)}
                  </Tag>
                ),
              },
              {
                title: '任务',
                dataIndex: 'job_name',
                width: 140,
                ellipsis: true,
              },
              {
                title: '开始时间',
                dataIndex: 'started_at',
                width: 150,
                render: (value) => dateTimeLabel(value),
              },
              {
                title: '采集 / 新增 / 更新',
                width: 130,
                align: 'right',
                render: (_, record) =>
                  `${record.items_seen} / ${record.items_created} / ${record.items_updated}`,
              },
              {
                title: '错误',
                dataIndex: 'error_message',
                ellipsis: true,
                render: (value) =>
                  value ? <Text type="danger">{value}</Text> : '-',
              },
            ]}
          />
        )}
      </Drawer>
    </PageContainer>
  );
};

export default SourcesPage;
