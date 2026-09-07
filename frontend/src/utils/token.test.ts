import { describe, expect, it } from 'vitest';
import {
  clearStoredToken,
  getStoredToken,
  notifySessionExpired,
  storeToken,
  SESSION_EXPIRED_EVENT,
} from './token';

describe('token 本地持久化', () => {
  it('存入后可读取同一令牌', () => {
    storeToken('token-abc');
    expect(getStoredToken()).toBe('token-abc');
  });

  it('清除后读取为空', () => {
    storeToken('token-abc');
    clearStoredToken();
    expect(getStoredToken()).toBeNull();
  });

  it('初始状态无令牌', () => {
    clearStoredToken();
    expect(getStoredToken()).toBeNull();
  });
});

describe('会话过期事件', () => {
  it('派发全局 session-expired 事件', () => {
    let fired = false;
    const handler = () => {
      fired = true;
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, handler);
    try {
      notifySessionExpired();
      expect(fired).toBe(true);
    } finally {
      window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
    }
  });
});
