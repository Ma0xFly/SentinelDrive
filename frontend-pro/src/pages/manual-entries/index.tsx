import PlaceholderPage from '@/components/PlaceholderPage';
import React from 'react';

/** 手工录入页面占位，由核心页面迁移任务实现。 */
const ManualEntriesPage: React.FC = () => (
  <PlaceholderPage
    title="手工录入"
    description="手工登记漏洞、告警、事件等安全情报，纳入统一归一化与评分流程。"
    plannedTask="Task 9.3"
  />
);

export default ManualEntriesPage;
