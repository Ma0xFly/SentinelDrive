import { beforeEach, describe, expect, it, vi } from 'vitest';

const historyReplace = vi.fn();
const messageError = vi.fn();

vi.mock('@umijs/max', () => ({
  history: {
    location: { pathname: '/alerts', search: '', hash: '' },
    replace: (...args: unknown[]) => historyReplace(...args),
  },
}));

vi.mock('antd', () => ({
  message: { error: (...args: unknown[]) => messageError(...args) },
}));

import { errorConfig } from './requestErrorConfig';
import {
  clearStoredToken,
  getStoredToken,
  SESSION_EXPIRED_EVENT,
} from '@/utils/token';

type ErrorHandler = (error: any, opts?: any) => void;

const errorHandler = errorConfig.errorConfig?.errorHandler as
  | ErrorHandler
  | undefined;

function storeTestToken(token: string) {
  window.localStorage.setItem('sentineldrive.access_token', token);
}

describe('统一错误处理的 401 行为', () => {
  beforeEach(() => {
    clearStoredToken();
    historyReplace.mockClear();
    messageError.mockClear();
  });

  it('401 时清除令牌、派发过期事件并携带回跳地址跳转登录页', () => {
    storeTestToken('token-401');
    const expiredListener = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, expiredListener);
    try {
      errorHandler?.({ response: { status: 401, data: {} } }, {});
      expect(getStoredToken()).toBeNull();
      expect(expiredListener).toHaveBeenCalledTimes(1);
      expect(historyReplace).toHaveBeenCalledWith(
        '/user/login?redirect=%2Falerts',
      );
      expect(messageError).not.toHaveBeenCalled();
    } finally {
      window.removeEventListener(SESSION_EXPIRED_EVENT, expiredListener);
    }
  });

  it('非 401 错误优先展示后端中文消息且不清令牌', () => {
    storeTestToken('token-keep');
    errorHandler?.(
      {
        response: {
          status: 422,
          data: {
            detail: { error: { code: 'x', message: '提交内容未通过校验' } },
          },
        },
      },
      {},
    );
    expect(messageError).toHaveBeenCalledWith('提交内容未通过校验');
    expect(getStoredToken()).toBe('token-keep');
    expect(historyReplace).not.toHaveBeenCalled();
  });

  it('后端消息缺失时按状态码给出默认中文提示', () => {
    errorHandler?.({ response: { status: 403, data: null } }, {});
    expect(messageError).toHaveBeenCalledWith(
      '当前账号没有执行此操作的权限。',
    );
  });

  it('skipErrorHandler 时直接抛出原始错误', () => {
    const raw = new Error('raw');
    expect(() => errorHandler?.(raw, { skipErrorHandler: true })).toThrow(raw);
  });
});

describe('请求拦截器附加鉴权头', () => {
  it('有令牌时附加 Bearer Authorization 头', async () => {
    storeTestToken('token-header');
    const interceptors = errorConfig.requestInterceptors ?? [];
    const interceptor = interceptors[0] as (config: any) => any;
    const config = interceptor({ headers: {} });
    expect(config.headers.Authorization).toBe('Bearer token-header');
  });

  it('无令牌时不附加鉴权头', () => {
    clearStoredToken();
    const interceptors = errorConfig.requestInterceptors ?? [];
    const interceptor = interceptors[0] as (config: any) => any;
    const config = interceptor({ headers: {} });
    expect(config.headers.Authorization).toBeUndefined();
  });
});
