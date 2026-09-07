/**
 * @name 中文安全运营台导航
 * 态势总览由仪表盘任务实现；其余页面由页面迁移任务实现，
 * 当前均为空态占位页。
 * 菜单名使用中文直接量（与官方精简脚本做法一致），
 * 语言包与 i18n 框架能力保留。
 */
export default [
  {
    path: '/user',
    layout: false,
    routes: [
      {
        name: '登录',
        path: '/user/login',
        component: './user/login',
      },
    ],
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: '态势总览',
    icon: 'dashboard',
    component: './dashboard',
  },
  {
    path: '/intelligence',
    routes: [
      {
        path: '/intelligence',
        name: '威胁情报',
        icon: 'global',
        component: './intelligence',
      },
      {
        path: '/intelligence/:id',
        name: '情报详情',
        hideInMenu: true,
        component: './intelligence/detail',
      },
    ],
  },
  {
    path: '/alerts',
    name: '告警',
    icon: 'alert',
    component: './alerts',
  },
  {
    path: '/sources',
    name: '数据源',
    icon: 'cloudServer',
    component: './sources',
  },
  {
    path: '/manual-entries',
    name: '手工录入',
    icon: 'form',
    component: './manual-entries',
  },
  {
    path: '/users',
    name: '用户管理',
    icon: 'team',
    access: 'canAdmin',
    component: './users',
  },
  {
    path: '*',
    layout: false,
    component: './exception/404',
  },
];
