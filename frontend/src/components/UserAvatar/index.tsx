import { LogoutOutlined, UserOutlined } from '@ant-design/icons';
import { history, useModel } from '@umijs/max';
import { Avatar, Button, Space, Tag } from 'antd';
import React, { startTransition } from 'react';
import { logout as logoutApi } from '@/services/auth';
import { clearStoredToken } from '@/utils/token';
import HeaderDropdown from '../HeaderDropdown';

const loginPath = '/user/login';

function getLoginUrl(): string {
  const { pathname, search, hash } = history.location;
  if (pathname === loginPath) {
    return loginPath;
  }
  return `${loginPath}?redirect=${encodeURIComponent(pathname + search + hash)}`;
}

/**
 * 顶部导航用户区：登录用户展示头像下拉（退出登录）；
 * 访客（未登录）展示「访客模式」提示与登录入口。
 */
export const UserAvatar: React.FC = () => {
  const { initialState, setInitialState } = useModel('@@initialState');
  const currentUser = initialState?.currentUser;

  if (!currentUser) {
    return (
      <Space size={8} style={{ padding: '0 8px' }}>
        <Tag color="default" style={{ marginInlineEnd: 0 }}>
          访客模式
        </Tag>
        <Button
          size="small"
          type="primary"
          icon={<UserOutlined />}
          onClick={() => {
            history.push(getLoginUrl());
          }}
        >
          登录
        </Button>
      </Space>
    );
  }

  const displayName = currentUser.display_name || currentUser.email.split('@')[0];

  const onMenuClick = async ({ key }: { key: string }) => {
    if (key !== 'logout') {
      return;
    }
    try {
      await logoutApi({ skipErrorHandler: true });
    } catch {
      // 后端注销失败不阻塞本地登出
    }
    clearStoredToken();
    startTransition(() => {
      setInitialState((s) => ({ ...s, currentUser: undefined }));
    });
    if (history.location.pathname !== loginPath) {
      history.replace(loginPath);
    }
  };

  return (
    <HeaderDropdown
      placement="bottomRight"
      menu={{
        selectedKeys: [],
        onClick: onMenuClick,
        items: [
          {
            key: 'logout',
            icon: <LogoutOutlined />,
            label: '退出登录',
          },
        ],
      }}
      arrow
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8,
          cursor: 'pointer',
          padding: '0 8px',
        }}
      >
        <Avatar size="small" icon={<UserOutlined />} />
        <span>{displayName}</span>
      </span>
    </HeaderDropdown>
  );
};

export default UserAvatar;