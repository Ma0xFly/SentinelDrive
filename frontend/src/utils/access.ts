/**
 * 访客只读访问控制：公开页面未登录也可访问，其余页面要求登录。
 */

/** 公开只读页面路径前缀（未登录可访问） */
export const PUBLIC_PATHS = ['/dashboard', '/intelligence', '/sources'];

/**
 * 判断路径是否为公开只读页面。
 * 前缀匹配（如 /intelligence/:id、/sources/:id 均视为公开）。
 */
export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((path) => {
    if (pathname === path) {
      return true;
    }
    return pathname.startsWith(`${path}/`);
  });
}