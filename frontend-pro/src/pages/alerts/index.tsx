import PlaceholderPage from '@/components/PlaceholderPage';
import React from 'react';

/** 告警页面占位，由核心页面迁移任务实现。 */
const AlertsPage: React.FC = () => (
  <PlaceholderPage
    title="告警"
    description="查看与处置由告警规则触发的威胁告警，支持状态流转与备注。"
    plannedTask="Task 9.3"
  />
);

export default AlertsPage;
