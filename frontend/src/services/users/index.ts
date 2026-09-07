import { request } from '@umijs/max';

/** 用户列表（仅管理员） GET /users */
export async function listUsers(options?: { [key: string]: any }) {
  return request<API.CurrentUser[]>('/users', {
    method: 'GET',
    ...(options || {}),
  });
}

/** 创建用户 POST /users */
export async function createUser(
  body: API.UserCreateParams,
  options?: { [key: string]: any },
) {
  return request<API.CurrentUser>('/users', {
    method: 'POST',
    data: body,
    ...(options || {}),
  });
}

/** 更新用户启用状态 PATCH /users/{user_id}/status */
export async function updateUserStatus(
  userId: string,
  body: API.UserStatusUpdateParams,
  options?: { [key: string]: any },
) {
  return request<API.CurrentUser>(`/users/${userId}/status`, {
    method: 'PATCH',
    data: body,
    ...(options || {}),
  });
}
