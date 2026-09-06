import { DownloadOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { history, useParams } from '@umijs/max';
import {
  Alert,
  App,
  Button,
  Card,
  Descriptions,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import React, { useEffect, useState } from 'react';
import {
  attackSurfaceOptions,
  confidenceOptions,
  dateTimeLabel,
  exploitStatusOptions,
  intelligenceStatusOptions,
  intelligenceTypeOptions,
  labelFromOptions,
  riskLevelColor,
  riskLevelOptions,
  severityColor,
  severityOptions,
  vehicleComponentOptions,
} from '@/constants/labels';
import {
  exportIntelligenceMarkdown,
  exportSummaryPdf,
} from '@/services/exports';
import { getIntelligence } from '@/services/intelligence';
import { saveDownload } from '@/utils/download';

const { Paragraph, Text, Title } = Typography;

/**
 * 威胁情报详情：来源归因、领域字段、风险评分解释与关联告警。
 */
const IntelligenceDetailPage: React.FC = () => {
  const params = useParams<{ id: string }>();
  const { message } = App.useApp();
  const [detail, setDetail] = useState<API.IntelligenceDetail | undefined>(
    undefined,
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [exporting, setExporting] = useState(false);

  const load = async () => {
    if (!params.id) {
      return;
    }
    setLoading(true);
    setLoadError('');
    try {
      const result = await getIntelligence(params.id, {
        skipErrorHandler: true,
      });
      setDetail(result);
    } catch {
      setLoadError('情报详情加载失败，请稍后重试。');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  const handleExport = async (kind: 'markdown' | 'pdf') => {
    if (!detail) {
      return;
    }
    setExporting(true);
    try {
      const result =
        kind === 'markdown'
          ? await exportIntelligenceMarkdown(detail.id)
          : await exportSummaryPdf();
      saveDownload(result);
      message.success(
        kind === 'markdown'
          ? 'Markdown 导出已开始下载'
          : '汇总 PDF 导出已开始下载',
      );
    } catch {
      message.error('导出失败，请稍后重试。');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <PageContainer title="威胁情报详情">
        <Card>
          <Skeleton active paragraph={{ rows: 10 }} />
        </Card>
      </PageContainer>
    );
  }

  if (loadError || !detail) {
    return (
      <PageContainer title="威胁情报详情">
        <Alert
          type="error"
          showIcon
          message={loadError || '未找到该情报'}
          action={
            <Button size="small" onClick={load}>
              重试
            </Button>
          }
        />
      </PageContainer>
    );
  }

  const scoreEntries = Object.entries(detail.score_metadata || {});

  const baseItems = [
    {
      key: 'type',
      label: '类型',
      children: labelFromOptions(
        intelligenceTypeOptions,
        detail.intelligence_type,
      ),
    },
    { key: 'cve', label: 'CVE', children: detail.cve_id || '-' },
    { key: 'cwe', label: 'CWE', children: detail.cwe_id || '-' },
    {
      key: 'severity',
      label: '严重度',
      children: (
        <Tag color={severityColor[detail.severity]}>
          {labelFromOptions(severityOptions, detail.severity)}
        </Tag>
      ),
    },
    {
      key: 'cvss',
      label: 'CVSS 分',
      children: detail.cvss_score ?? '-',
    },
    {
      key: 'vector',
      label: 'CVSS 向量',
      children: (
        <Paragraph style={{ marginBottom: 0 }} copyable={!!detail.cvss_vector}>
          {detail.cvss_vector || '-'}
        </Paragraph>
      ),
    },
    { key: 'vendor', label: '厂商', children: detail.affected_vendor || '-' },
    { key: 'product', label: '产品', children: detail.affected_product || '-' },
    {
      key: 'version',
      label: '影响版本',
      children: detail.affected_version || '-',
    },
    {
      key: 'component',
      label: '车辆组件',
      children: labelFromOptions(
        vehicleComponentOptions,
        detail.vehicle_component,
      ),
    },
    {
      key: 'surface',
      label: '攻击面',
      children: labelFromOptions(attackSurfaceOptions, detail.attack_surface),
    },
    {
      key: 'exploit',
      label: '利用状态',
      children: labelFromOptions(exploitStatusOptions, detail.exploit_status),
    },
    {
      key: 'confidence',
      label: '可信度',
      children: labelFromOptions(confidenceOptions, detail.confidence),
    },
    {
      key: 'status',
      label: '状态',
      children: labelFromOptions(intelligenceStatusOptions, detail.status),
    },
    {
      key: 'tags',
      label: '标签',
      span: 2,
      children:
        detail.tags.length > 0 ? (
          <Space size={4} wrap>
            {detail.tags.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </Space>
        ) : (
          '-'
        ),
    },
  ];

  const riskItems = [
    {
      key: 'score',
      label: '风险分',
      children: <Text strong>{detail.risk_score ?? '-'}</Text>,
    },
    {
      key: 'level',
      label: '风险等级',
      children: (
        <Tag color={riskLevelColor[detail.risk_level]}>
          {labelFromOptions(riskLevelOptions, detail.risk_level)}
        </Tag>
      ),
    },
    {
      key: 'alerts',
      label: '关联告警',
      children: detail.related_alert_count,
    },
  ];

  return (
    <PageContainer
      title={detail.title}
      onBack={() => history.push('/intelligence')}
      extra={[
        <Button
          key="export-md"
          icon={<DownloadOutlined />}
          loading={exporting}
          onClick={() => handleExport('markdown')}
        >
          导出 Markdown
        </Button>,
        <Button
          key="export-pdf"
          icon={<DownloadOutlined />}
          loading={exporting}
          onClick={() => handleExport('pdf')}
        >
          导出汇总 PDF
        </Button>,
      ]}
    >
      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        <Card bordered={false} title="基础信息">
          <Descriptions column={3} size="small" items={baseItems} />
          {detail.summary && (
            <>
              <Title level={5} style={{ marginTop: 16 }}>
                摘要
              </Title>
              <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                {detail.summary}
              </Paragraph>
            </>
          )}
        </Card>

        <Card bordered={false} title="风险评估">
          <Descriptions column={3} size="small" items={riskItems} />
          {detail.score_explanation && (
            <>
              <Title level={5} style={{ marginTop: 16 }}>
                评分解释
              </Title>
              <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                {detail.score_explanation}
              </Paragraph>
            </>
          )}
          {scoreEntries.length > 0 && (
            <>
              <Title level={5} style={{ marginTop: 16 }}>
                评分因素
              </Title>
              <Descriptions
                size="small"
                column={3}
                bordered
                items={scoreEntries.map(([key, value]) => ({
                  key,
                  label: key,
                  children: (
                    <span style={{ wordBreak: 'break-all' }}>
                      {typeof value === 'string'
                        ? value
                        : JSON.stringify(value)}
                    </span>
                  ),
                }))}
              />
            </>
          )}
        </Card>

        <Card bordered={false} title="来源归因">
          <Table
            rowKey={(record, index) => `${record.source_url}-${index}`}
            size="small"
            pagination={false}
            dataSource={detail.sources}
            columns={[
              {
                title: '来源名称',
                dataIndex: 'source_name',
                width: 160,
                ellipsis: true,
              },
              {
                title: '来源 URL',
                dataIndex: 'source_url',
                ellipsis: true,
                render: (value) =>
                  value ? (
                    <a href={value} target="_blank" rel="noopener noreferrer">
                      {value}
                    </a>
                  ) : (
                    '-'
                  ),
              },
              {
                title: '外部编号',
                dataIndex: 'external_id',
                width: 160,
                ellipsis: true,
                render: (v) => v || '-',
              },
              {
                title: '首次发现',
                dataIndex: 'first_seen_at',
                width: 150,
                render: (v) => dateTimeLabel(v),
              },
              {
                title: '最近发现',
                dataIndex: 'last_seen_at',
                width: 150,
                render: (v) => dateTimeLabel(v),
              },
            ]}
          />
          <Descriptions
            size="small"
            column={2}
            style={{ marginTop: 16 }}
            items={[
              {
                key: 'dedup',
                label: '去重键',
                children: (
                  <span style={{ wordBreak: 'break-all' }}>
                    {detail.dedup_key}
                  </span>
                ),
              },
              {
                key: 'external',
                label: '外部编号集合',
                children: (
                  <span style={{ wordBreak: 'break-all' }}>
                    {Object.keys(detail.external_ids || {}).length > 0
                      ? JSON.stringify(detail.external_ids)
                      : '-'}
                  </span>
                ),
              },
            ]}
          />
        </Card>

        <Card
          bordered={false}
          title={`关联告警（${detail.related_alerts.length}）`}
        >
          {detail.related_alerts.length === 0 ? (
            <Text type="secondary">该情报暂未触发告警。</Text>
          ) : (
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={detail.related_alerts}
              columns={[
                { title: '告警标题', dataIndex: 'title', ellipsis: true },
                {
                  title: '风险等级',
                  dataIndex: 'risk_level',
                  width: 100,
                  render: (value) => (
                    <Tag color={riskLevelColor[value]}>
                      {labelFromOptions(riskLevelOptions, value)}
                    </Tag>
                  ),
                },
                {
                  title: '状态',
                  dataIndex: 'status',
                  width: 100,
                  render: (value) =>
                    labelFromOptions(intelligenceStatusOptions, value),
                },
                {
                  title: '触发时间',
                  dataIndex: 'triggered_at',
                  width: 160,
                  render: (value) => dateTimeLabel(value),
                },
              ]}
            />
          )}
        </Card>
      </Space>
    </PageContainer>
  );
};

export default IntelligenceDetailPage;
