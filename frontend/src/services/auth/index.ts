import { request } from '@umijs/max';

/** 登录并获取访问令牌 POST /auth/login */
export async function login(
  body: API.LoginParams,
  options?: { [key: string]: any },
) {
  return request<API.LoginResult>('/auth/login', {
    method: 'POST',
    data: body,
    skipErrorHandler: true,
    ...(options || {}),
  });
}

/** 注销当前会话 POST /auth/logout */
export async function logout(options?: { [key: string]: any }) {
  return request<{ status: string }>('/auth/logout', {
    method: 'POST',
    ...(options || {}),
  });
}

/** 获取当前登录用户 GET /auth/me */
export async function currentUser(options?: { [key: string]: any }) {
  return request<API.CurrentUser>('/auth/me', {
    method: 'GET',
    ...(options || {}),
  });
}
