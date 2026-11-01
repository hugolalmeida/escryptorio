import { defineConfig } from "@playwright/test";

const port = Number(process.env.CRYPTOLAB_TEST_PORT ?? "3100");
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Porta de teste inválida");

export default defineConfig({
  testDir: "./tests/ui", fullyParallel: true, retries: 0, workers: 2,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: `http://127.0.0.1:${port}`, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } } },
    { name: "tablet", use: { browserName: "chromium", viewport: { width: 820, height: 1180 } } },
    { name: "mobile", use: { browserName: "chromium", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: { command: `node node_modules/next/dist/bin/next start apps/web --hostname 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}`, reuseExistingServer: false, timeout: 60000 },
});
