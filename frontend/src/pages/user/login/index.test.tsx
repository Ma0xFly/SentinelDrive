import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { historyPush } = vi.hoisted(() => ({ historyPush: vi.fn() }));

vi.mock('@umijs/max', () => ({
  Helmet: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  history: {
    location: { pathname: '/user/login', search: '', hash: '' },
    push: (...args: unknown[]) => historyPush(...args),
  },
  useModel: () => ({ initialState: {}, setInitialState: vi.fn() }),
}));

vi.mock('@ant-design/pro-components', () => {
  const ProFormText: any = (props: any) => <input {...props} />;
  ProFormText.Password = (props: any) => <input type="password" {...props} />;
  return {
    LoginForm: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    ProFormText,
  };
});

vi.mock('@/components', () => ({ Footer: () => null }));
vi.mock('@/services/auth', () => ({ login: vi.fn() }));
vi.mock('@/utils/token', () => ({ storeToken: vi.fn() }));

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return {
    ...actual,
    App: {
      ...actual.App,
      useApp: () => ({ message: { success: vi.fn(), error: vi.fn() } }),
    },
  };
});

import Login from './index';

describe('登录页访客入口', () => {
  beforeEach(() => {
    historyPush.mockClear();
  });

  it('展示「以访客身份浏览」入口', () => {
    render(<Login />);
    expect(screen.getByRole('button', { name: /以访客身份浏览/ })).toBeTruthy();
  });

  it('点击访客入口跳转到态势总览', () => {
    render(<Login />);
    fireEvent.click(screen.getByRole('button', { name: /以访客身份浏览/ }));
    expect(historyPush).toHaveBeenCalledWith('/dashboard');
  });
});