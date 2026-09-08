import { describe, expect, it } from 'vitest';
import { isPublicPath } from './access';

describe('isPublicPath 访客公开页判定', () => {
  it('精确匹配公开页面', () => {
    expect(isPublicPath('/dashboard')).toBe(true);
    expect(isPublicPath('/intelligence')).toBe(true);
    expect(isPublicPath('/sources')).toBe(true);
  });

  it('公开页面的子路径（如详情页）同样公开', () => {
    expect(isPublicPath('/intelligence/00000000-0000-0000-0000-000000000001')).toBe(true);
    expect(isPublicPath('/sources/00000000-0000-0000-0000-000000000001')).toBe(true);
  });

  it('受保护页面返回 false', () => {
    expect(isPublicPath('/alerts')).toBe(false);
    expect(isPublicPath('/manual-entries')).toBe(false);
    expect(isPublicPath('/users')).toBe(false);
    expect(isPublicPath('/user/login')).toBe(false);
    expect(isPublicPath('/')).toBe(false);
  });

  it('前缀相似但不属于公开页的路径不误判', () => {
    expect(isPublicPath('/intelligence-extra')).toBe(false);
    expect(isPublicPath('/sources-archive')).toBe(false);
  });
});