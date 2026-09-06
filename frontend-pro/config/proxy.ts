/**
 * @name 代理的配置
 * 本地开发时把 /api 请求转发到本机后端服务。
 * 生产环境中由反向代理（Caddy）把 /api/* 转发到 backend 服务，
 * 此配置不生效。
 * @doc https://umijs.org/docs/guides/proxy
 */
export default {
  dev: {
    '/api/': {
      target: process.env.BACKEND_PROXY_TARGET || 'http://localhost:8000',
      changeOrigin: true,
    },
  },
};
