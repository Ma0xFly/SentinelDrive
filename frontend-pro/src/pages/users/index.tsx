import PlaceholderPage from '@/components/PlaceholderPage';
import React from 'react';

/** 用户管理页面占位，由核心页面迁移任务实现，仅管理员可见。 */
const UsersPage: React.FC = () => (
  <PlaceholderPage
    title="用户管理"
    description="管理系统账号的创建与启用状态，仅对管理员开放。"
    plannedTask="Task 9.3"
  />
);

export default UsersPage;
