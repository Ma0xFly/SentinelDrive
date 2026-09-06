import type { Settings as LayoutSettings } from '@ant-design/pro-components';
import type { RequestConfig, RunTimeLayoutConfig } from '@umijs/max';
import { history } from '@umijs/max';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
import relativeTime from 'dayjs/plugin/relativeTime';
import React from 'react';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

import { ErrorBoundary, Footer, OfflineBanner, UserAvatar } from '@/components';
import { currentUser as queryCurrentUser } from '@/services/auth';
import defaultSettings from '../config/defaultSettings';
import { errorConfig } from './requestErrorConfig';
import { clearStoredToken } from '@/utils/token';

const loginPath = '/user/login';

/**
 * @see https://umijs.org/docs/api/runtime-config#getinitialstate
 */
export async function getInitialState(): Promise<{
  settings?: Partial<LayoutSettings>;
  currentUser?: API.CurrentUser;
  fetchUserInfo?: () => Promise<API.CurrentUser | undefined>;
}> {
  const fetchUserInfo = async () => {
    try {
      const user = await queryCurrentUser({ skipErrorHandler: true });
      return user;
    } catch (_error) {
      clearStoredToken();
      const { pathname, search, hash } = history.location;
      if (pathname !== loginPath) {
        history.replace(
          `${loginPath}?redirect=${encodeURIComponent(pathname + search + hash)}`,
        );
      }
      return undefined;
    }
  };

  // 登录页不做用户信息预取，其余页面进入时先恢复会话
  if (history.location.pathname !== loginPath) {
    const currentUser = await fetchUserInfo();
    return {
      fetchUserInfo,
      currentUser,
      settings: defaultSettings as Partial<LayoutSettings>,
    };
  }
  return {
    fetchUserInfo,
    settings: defaultSettings as Partial<LayoutSettings>,
  };
}

// ProLayout 运行时配置 https://procomponents.ant.design/components/layout
export const layout: RunTimeLayoutConfig = ({ initialState }) => {
  return {
    avatarProps: {
      render: () => <UserAvatar />,
    },
    footerRender: () => <Footer />,
    onPageChange: () => {
      const { location } = history;
      // 路由守卫：未登录访问受保护页面时回到登录页
      if (!initialState?.currentUser && location.pathname !== loginPath) {
        clearStoredToken();
        history.replace(
          `${loginPath}?redirect=${encodeURIComponent(location.pathname + location.search + location.hash)}`,
        );
      }
    },
    // 用统一的离线感知 ErrorBoundary 替换 ProLayout 默认实现
    ErrorBoundary,
    menuHeaderRender: undefined,
    ...initialState?.settings,
  };
};

/**
 * @name request 配置：统一 baseURL 与错误处理
 * @doc https://umijs.org/docs/max/request#配置
 */
export const request: RequestConfig = {
  baseURL: '/api',
  ...errorConfig,
};

export function rootContainer(container: React.ReactNode) {
  return (
    <>
      <OfflineBanner />
      <ErrorBoundary>{container}</ErrorBoundary>
    </>
  );
}
