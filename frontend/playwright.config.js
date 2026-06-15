const { defineConfig, devices } = require("@playwright/test");

process.env.NO_PROXY = appendNoProxy(process.env.NO_PROXY);
process.env.no_proxy = appendNoProxy(process.env.no_proxy);

module.exports = defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  expect: {
    timeout: 5000
  },
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off"
  },
  webServer: {
    command: "NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost npx next dev -H 127.0.0.1 -p 3000",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120000
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});

function appendNoProxy(value) {
  const localHosts = "127.0.0.1,localhost";
  return value ? `${value},${localHosts}` : localHosts;
}
