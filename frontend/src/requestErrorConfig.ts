import type { RequestOptions } from '@@/plugin-request/request';
import type { RequestConfig } from '@umijs/max';
import { history } from '@umijs/max';
import { message } from 'antd';
import {
  clearStoredToken,
  getStoredToken,
  notifySessionExpired,
} from '@/utils/token';

const loginPath = '/user/login';

/** 各状态码的默认中文提示 */
const STATUS_MESSAGES: Record<number, string> = {
  400: '请求参数不正确，请检查后重试。',
  401: '登录状态已过期，请重新登录。',
  403: '当前账号没有执行此操作的权限。',
  404: '请求的资源不存在。',
  409: '请求与现有数据冲突，请检查后重试。',
  422: '提交内容未通过校验，请检查字段后重试。',
  429: '请求过于频繁，请稍后重试。',
};

/**
 * 从后端错误响应中提取用户可读的中文消息。
 * 后端约定形如 { detail: { error: { code, message } } }，兼容纯字符串 detail。
 */
function extractServerMessage(data: any): string | null {
  const candidates = [data?.detail?.error, data?.error, data?.detail, data?.message];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim();
    }
    if (typeof candidate?.message === 'string' && candidate.message.trim()) {
      return candidate.message.trim();
    }
  }
  return null;
}

/**
 * 统一 401 处理：清除本地凭证并回到登录页，携带原路径便于登录后回跳。
 */
function handleUnauthorized() {
  clearStoredToken();
  notifySessionExpired();
  const { pathname, search, hash } = history.location;
  if (pathname !== loginPath) {
    const redirect = encodeURIComponent(pathname + search + hash);
    history.replace(`${loginPath}?redirect=${redirect}`);
  }
}

export const errorConfig: RequestConfig = {
  errorConfig: {
    errorHandler: (error: any, opts: any) => {
      if (opts?.skipErrorHandler) {
        throw error;
      }
      const status: number | undefined = error?.response?.status;
      // 统一会话过期处理：清凭证、跳登录页
      if (status === 401) {
        handleUnauthorized();
        return;
      }
      const serverMessage = extractServerMessage(error?.response?.data);
      if (serverMessage) {
        message.error(serverMessage);
        return;
      }
      if (error?.response) {
        message.error(STATUS_MESSAGES[status ?? 0] || '请求失败，请稍后重试。');
        return;
      }
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        message.error('网络不可用，请检查网络连接后重试。');
        return;
      }
      message.error('无法连接后端服务，请检查网络或服务状态。');
    },
  },

  requestInterceptors: [
    (config: RequestOptions) => {
      const token = getStoredToken();
      if (token) {
        config.headers = {
          ...config.headers,
          Authorization: `Bearer ${token}`,
        };
      }
      return config;
    },
  ],

  responseInterceptors: [],
};
