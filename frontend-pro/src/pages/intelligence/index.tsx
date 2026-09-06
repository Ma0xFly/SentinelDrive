import PlaceholderPage from '@/components/PlaceholderPage';
import React from 'react';

/** 威胁情报页面占位，由核心页面迁移任务实现。 */
const IntelligencePage: React.FC = () => (
  <PlaceholderPage
    title="威胁情报"
    description="检索与查看已归一化入库的车联网威胁情报，含来源归因与风险评分。"
    plannedTask="Task 9.3"
  />
);

export default IntelligencePage;
