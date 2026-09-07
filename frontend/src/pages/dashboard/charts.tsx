import { Area, Bar, Pie } from '@ant-design/charts';
import React from 'react';
import {
  alertStatusOptions,
  intelligenceTypeOptions,
  labelFromOptions,
  severityOptions,
} from '@/constants/labels';

export interface DistributionEntry {
  key: string;
  type: string;
  value: number;
}

function toDistributionData(
  distribution: Record<string, number>,
  options: [string, string][],
  { dropZero }: { dropZero: boolean },
): DistributionEntry[] {
  return Object.entries(distribution)
    .map(([key, value]) => ({ key, type: labelFromOptions(options, key), value }))
    .filter((item) => (dropZero ? item.value > 0 : true));
}

/** 近 30 天情报新增趋势（面积图） */
export const TrendArea: React.FC<{ trend: API.StatsTrendPoint[] }> = ({ trend }) => (
  <Area
    data={trend.map((point) => ({ date: point.date.slice(5), count: point.count }))}
    xField="date"
    yField="count"
    height={260}
    autoFit
    shapeField="smooth"
    style={{
      fill: 'linear-gradient(0deg, rgba(22,119,255,0.30), rgba(22,119,255,0.04))',
    }}
    axis={{
      x: { title: false, labelAutoRotate: false },
      y: { title: false },
    }}
  />
);

/** 严重度分布（环图，零值项不展示） */
export const SeverityPie: React.FC<{ distribution: Record<string, number> }> = ({
  distribution,
}) => (
  <Pie
    data={toDistributionData(distribution, severityOptions, { dropZero: true })}
    angleField="value"
    colorField="type"
    height={260}
    autoFit
    innerRadius={0.55}
    legend={{ color: { position: 'bottom' } }}
    tooltip={{ items: [{ channel: 'y', name: '数量' }] }}
  />
);

/** 情报类型占比（横向条形，枚举全量展示） */
export const TypeBar: React.FC<{ distribution: Record<string, number> }> = ({
  distribution,
}) => (
  <Bar
    data={toDistributionData(distribution, intelligenceTypeOptions, { dropZero: false })}
    xField="type"
    yField="value"
    height={260}
    autoFit
    coordinate={{ transform: [{ type: 'transpose' }] }}
    axis={{ x: { title: false, labelAutoRotate: true }, y: { title: false } }}
  />
);

/** 告警状态分布（横向条形，枚举全量展示） */
export const AlertStatusBar: React.FC<{ distribution: Record<string, number> }> = ({
  distribution,
}) => (
  <Bar
    data={toDistributionData(distribution, alertStatusOptions, { dropZero: false })}
    xField="type"
    yField="value"
    height={260}
    autoFit
    coordinate={{ transform: [{ type: 'transpose' }] }}
    axis={{ x: { title: false, labelAutoRotate: true }, y: { title: false } }}
  />
);

/** 来源情报覆盖 Top 10（横向条形） */
export const SourceTopBar: React.FC<{ top: API.StatsSourceTop[] }> = ({ top }) => (
  <Bar
    data={top.map((item) => ({ type: item.name, value: item.intelligence_count }))}
    xField="type"
    yField="value"
    height={260}
    autoFit
    coordinate={{ transform: [{ type: 'transpose' }] }}
    axis={{ x: { title: false, labelAutoRotate: true }, y: { title: false } }}
  />
);
