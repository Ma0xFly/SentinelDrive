/**
 * @see https://umijs.org/docs/max/access#access
 */
export default function access(
  initialState: { currentUser?: API.CurrentUser } | undefined,
) {
  const { currentUser } = initialState ?? {};
  const isAuthenticated = !!currentUser;
  return {
    // 登录用户可操作的页面（访客不可见/不可达）
    canOperate: isAuthenticated,
    // 仅管理员
    canAdmin: isAuthenticated && currentUser.is_admin,
  };
}