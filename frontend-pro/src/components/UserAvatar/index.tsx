import { LogoutOutlined, UserOutlined } from '@ant-design/icons';
import { history, useModel } from '@umijs/max';
import { Avatar, Spin } from 'antd';
import React, { startTransition } from 'react';
import { logout as logoutApi } from '@/services/auth';
import { clearStoredToken } from '@/utils/token';
import HeaderDropdown from '../HeaderDropdown';

const loginPath = '/user/login';

/**
 * 顶部导航的用户头像下拉：展示当前账号并提供退出登录。
 */
export const UserAvatar: React.FC = () => {
  const { initialState, setInitialState } = useModel('@@initialState');
  const currentUser = initialState?.currentUser;

  if (!currentUser) {
    return <Spin size="small" style={{ marginLeft: 8, marginRight: 8 }} />;
  }

  const displayName =
    currentUser.display_name || currentUser.email.split('@')[0];

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
