import { PageContainer } from '@ant-design/pro-components';
import { Card, Empty, Typography } from 'antd';
import React from 'react';

const { Text, Title } = Typography;

export interface PlaceholderPageProps {
  /** 页面中文标题 */
  title: string;
  /** 页面职责的一句话说明 */
  description: string;
  /** 实现该页面的后续迭代任务编号 */
  plannedTask: string;
}

/**
 * 功能页面空态占位：仅说明页面定位与实现安排，不展示任何虚构数据。
 */
const PlaceholderPage: React.FC<PlaceholderPageProps> = ({
  title,
  description,
  plannedTask,
}) => {
  return (
    <PageContainer title={false}>
      <Card bordered={false}>
        <Title level={4} style={{ marginTop: 0 }}>
          {title}
        </Title>
        <Text type="secondary">{description}</Text>
        <Empty
          style={{ marginTop: 32, marginBottom: 32 }}
          description={`该页面由 ${plannedTask} 实现，当前为占位页`}
        />
      </Card>
    </PageContainer>
  );
};

export default PlaceholderPage;
