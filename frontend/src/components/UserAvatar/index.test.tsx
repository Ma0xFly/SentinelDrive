import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockModel, historyPush } = vi.hoisted(() => ({
  mockModel: { value: {} },
  historyPush: vi.fn(),
}));

vi.mock('@umijs/max', () => ({
  history: {
    location: { pathname: '/intelligence', search: '', hash: '' },
    push: (...args: unknown[]) => historyPush(...args),
  },
  useModel: () => mockModel.value,
}));

vi.mock('@/services/auth', () => ({
  logout: vi.fn().mockResolvedValue({ status: 'ok' }),
}));

vi.mock('@/utils/token', () => ({
  clearStoredToken: vi.fn(),
}));

import UserAvatar from './index';

describe('UserAvatar 访客/登录双态', () => {
  beforeEach(() => {
    historyPush.mockClear();
  });

  it('未登录（访客）时展示访客模式提示与登录入口', () => {
    mockModel.value = { initialState: { currentUser: undefined } };
    render(<UserAvatar />);
    expect(screen.getByText('访客模式')).toBeTruthy();
    expect(screen.getByRole('button', { name: /登录/ })).toBeTruthy();
  });

  it('访客点击登录跳转到带 redirect 的登录页', () => {
    mockModel.value = { initialState: { currentUser: undefined } };
    render(<UserAvatar />);
    fireEvent.click(screen.getByRole('button', { name: /登录/ }));
    expect(historyPush).toHaveBeenCalledWith(
      '/user/login?redirect=%2Fintelligence',
    );
  });

  it('登录用户展示邮箱前缀，不显示访客提示', () => {
    mockModel.value = {
      initialState: {
        currentUser: { display_name: null, email: 'admin@example.test', is_admin: true },
      },
    };
    render(<UserAvatar />);
    expect(screen.getByText('admin')).toBeTruthy();
    expect(screen.queryByText('访客模式')).toBeNull();
    expect(screen.queryByRole('button', { name: /登录/ })).toBeNull();
  });
});