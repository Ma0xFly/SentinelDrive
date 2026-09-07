import { ReloadOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import { Alert, Button, Card, Col, Empty, Row, Skeleton, Statistic } from 'antd';
import React, { Suspense, useCallback, useEffect, useState } from 'react';
import { getStatsOverview } from '@/services/stats';

const TrendArea = React.lazy(() =>
  import('./charts').then((m) => ({ default: m.TrendArea })),
);
const SeverityPie = React.lazy(() =>
  import('./charts').then((m) => ({ default: m.SeverityPie })),
);
const TypeBar = React.lazy(() =>
  import('./charts').then((m) => ({ default: m.TypeBar })),
);
const AlertStatusBar = React.lazy(() =>
  import('./charts').then((m) => ({ default: m.AlertStatusBar })),
);
const SourceTopBar = React.lazy(() =>
  import('./charts').then((m) => ({ default: m.SourceTopBar })),
);

const ChartFallback: React.FC<{ height: number }> = ({ height }) => (
  <Skeleton active paragraph={{ rows: 3 }} style={{ height }} title={false} />
);

/**
 * 态势总览仪表盘：情报与告警的总量、分布与趋势统计。
 */
const DashboardPage: React.FC = () => {
  const [overview, setOverview] = useState<API.StatsOverview>();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      const result = await getStatsOverview({ skipErrorHandler: true });
      setOverview(result);
    } catch {
      setLoadError('态势统计数据加载失败，请检查后端服务状态后重试。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const totals = overview?.totals;
  const isEmpty =
    !!overview && overview.totals.total_intelligence === 0 && overview.alerts.total === 0;

  const chartSkeleton = (node: React.ReactNode, height = 260) => (
    <Suspense fallback={<ChartFallback height={height} />}>{node}</Suspense>
  );

  return (
    <PageContainer
      title="态势总览"
      subTitle="威胁情报与告警的总量、分布与趋势"
      extra={[
        <Button key="refresh" icon={<ReloadOutlined />} loading={loading} onClick={load}>
          刷新
        </Button>,
      ]}
    >
      {loadError && (
        <Alert
          type="error"
          showIcon
          message={loadError}
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={load}>
              重试
            </Button>
          }
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card bordered={false} loading={loading}>
            <Statistic
              title="情报总数"
              value={totals?.total_intelligence ?? 0}
              suffix={<span style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)' }}>条</span>}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>
              近 24 小时新增 {totals?.new_last_24_hours ?? 0} 条
            </div>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card bordered={false} loading={loading}>
            <Statistic
              title="近 7 天新增情报"
              value={totals?.new_last_7_days ?? 0}
              suffix={<span style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)' }}>条</span>}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card bordered={false} loading={loading}>
            <Statistic
              title="告警总数"
              value={overview?.alerts.total ?? 0}
              suffix={<span style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)' }}>条</span>}
            />
            <div style={{ marginTop: 8, fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>
              未确认告警 {overview?.alerts.by_status.open ?? 0} 条
            </div>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card bordered={false} loading={loading}>
            <Statistic
              title="启用中数据源"
              value={overview?.sources.enabled ?? 0}
              suffix={<span style={{ fontSize: 13, color: 'rgba(0,0,0,0.45)' }}>个</span>}
            />
          </Card>
        </Col>
      </Row>

      {isEmpty && !loading && (
        <Card bordered={false} style={{ marginTop: 16 }}>
          <Empty description="暂无统计数据，情报与告警入库后将在此展示态势图表" />
        </Card>
      )}

      {!isEmpty && overview && (
        <>
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={16}>
              <Card bordered={false} title="近 30 天情报新增趋势">
                {chartSkeleton(<TrendArea trend={overview.trend} />)}
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card bordered={false} title="严重度分布">
                {chartSkeleton(<SeverityPie distribution={overview.by_severity} />)}
              </Card>
            </Col>
          </Row>
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={8}>
              <Card bordered={false} title="情报类型占比">
                {chartSkeleton(<TypeBar distribution={overview.by_intelligence_type} />)}
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card bordered={false} title="告警状态分布">
                {chartSkeleton(<AlertStatusBar distribution={overview.alerts.by_status} />)}
              </Card>
            </Col>
            <Col xs={24} lg={8}>
              <Card bordered={false} title="来源情报覆盖 Top 10">
                {overview.sources.top.length > 0 ? (
                  chartSkeleton(<SourceTopBar top={overview.sources.top} />)
                ) : (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无来源关联数据"
                    style={{ padding: '48px 0' }}
                  />
                )}
              </Card>
            </Col>
          </Row>
        </>
      )}
    </PageContainer>
  );
};

export default DashboardPage;
