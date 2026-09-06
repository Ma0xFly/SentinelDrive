/**
 * @name 代理的配置
 * 本地开发时把 /api 请求转发到本机后端服务，并剥离 /api 前缀
 * （与生产环境 Caddy handle_path /api/* 的转发语义一致）。
 * 生产环境中由反向代理完成该转发，此配置不生效。
 * @doc https://umijs.org/docs/guides/proxy
 */
export default {
  dev: {
    '/api/': {
      target: process.env.BACKEND_PROXY_TARGET || 'http://localhost:8000',
      changeOrigin: true,
      pathRewrite: { '^/api': '' },
    },
  },
};
