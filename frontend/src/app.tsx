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
import { clearStoredToken, getStoredToken } from '@/utils/token';
import { isPublicPath } from '@/utils/access';
import defaultSettings from '../config/defaultSettings';
import { errorConfig } from './requestErrorConfig';

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
      return undefined;
    }
  };

  const { pathname } = history.location;
  // 登录页不做用户信息预取
  if (pathname === loginPath) {
    return {
      fetchUserInfo,
      settings: defaultSettings as Partial<LayoutSettings>,
    };
  }

  // 公开页：无令牌直接以访客进入；有令牌尝试恢复会话，
  // 令牌失效则静默降级为访客，不强制跳登录。
  if (isPublicPath(pathname)) {
    const currentUser = getStoredToken() ? await fetchUserInfo() : undefined;
    return {
      fetchUserInfo,
      currentUser,
      settings: defaultSettings as Partial<LayoutSettings>,
    };
  }

  // 受保护页：必须登录，未登录或令牌失效跳登录并携带回跳地址
  if (!getStoredToken()) {
    history.replace(
      `${loginPath}?redirect=${encodeURIComponent(pathname + history.location.search + history.location.hash)}`,
    );
    return {
      fetchUserInfo,
      settings: defaultSettings as Partial<LayoutSettings>,
    };
  }
  const currentUser = await fetchUserInfo();
  if (!currentUser) {
    history.replace(
      `${loginPath}?redirect=${encodeURIComponent(pathname + history.location.search + history.location.hash)}`,
    );
  }
  return {
    fetchUserInfo,
    currentUser,
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
      // 路由守卫：受保护页面未登录时回到登录页；公开页放行访客
      if (
        !initialState?.currentUser &&
        location.pathname !== loginPath &&
        !isPublicPath(location.pathname)
      ) {
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