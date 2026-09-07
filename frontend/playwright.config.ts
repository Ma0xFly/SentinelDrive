import { defineConfig, devices } from '@playwright/test';

const port = process.env.PLAYWRIGHT_PORT || '8000';
const baseURL = `http://127.0.0.1:${port}`;

// 浏览器访问时把 /api 请求的转发目标指向一个不会响应的地址：
// E2E 用 page.route 在浏览器侧拦截 /api/*，proxy 不会真正被用到。
// 若 mock 漏掉某条请求，这里会让它立刻失败而不是命中本机后端。
const backendProxyTarget = process.env.BACKEND_PROXY_TARGET || 'http://127.0.0.1:1';

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  webServer: {
    command: `cross-env UMI_ENV=dev MOCK=none BACKEND_PROXY_TARGET=${backendProxyTarget} PORT=${port} max dev`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
