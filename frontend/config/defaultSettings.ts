import type { ProLayoutProps } from '@ant-design/pro-components';

/**
 * 布局默认设置：亮色、侧边导航、固定头部的安全运营工作台风格。
 */
const Settings: ProLayoutProps & {
  logo?: string;
} = {
  navTheme: 'light',
  colorPrimary: '#1677ff',
  layout: 'side',
  contentWidth: 'Fluid',
  fixedHeader: true,
  fixSiderbar: true,
  colorWeak: false,
  title: 'SentinelDrive 安全运营台',
  logo: '/logo.svg',
  iconfontUrl: '',
  token: {},
};

export default Settings;
