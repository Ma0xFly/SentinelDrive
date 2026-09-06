import PlaceholderPage from '@/components/PlaceholderPage';
import React from 'react';

/** 数据源页面占位，由核心页面迁移任务实现。 */
const SourcesPage: React.FC = () => (
  <PlaceholderPage
    title="数据源"
    description="查看采集数据源状态、任务日志与采集管道运行情况。"
    plannedTask="Task 9.3"
  />
);

export default SourcesPage;
