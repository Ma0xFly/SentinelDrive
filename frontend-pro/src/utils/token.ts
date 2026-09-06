/**
 * 访问令牌的本地持久化与全局会话过期事件。
 * 令牌仅存于 localStorage；注销或收到 401 时清除。
 */
const TOKEN_STORAGE_KEY = 'sentineldrive.access_token';

/** 全局会话过期事件名：收到 401 时派发，应用层监听后跳转登录页。 */
export const SESSION_EXPIRED_EVENT = 'sentineldrive:session-expired';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function storeToken(token: string): void {
  if (typeof window !== 'undefined' && token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }
}

export function clearStoredToken(): void {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export function notifySessionExpired(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
  }
}
