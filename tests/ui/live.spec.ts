import { expect, test } from "@playwright/test";

test("smoke real: worker → SQLite → FastAPI → Next → gráfico", async ({ page, request }, testInfo) => {
  test.skip(process.env.CRYPTOLAB_LIVE_SMOKE !== "1", "Requer worker e backend locais ativos, sem mocks.");
  const response = await request.get("/api/market?symbol=BTCUSDT&interval=60");
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  expect(data.source).toBe("Bybit");
  expect(data.category).toBe("spot");
  expect(data.stale).toBe(false);
  expect(data.live_trading_enabled).toBe(false);
  expect(data.candles.length).toBe(300);
  for (const symbol of ["BTCUSDT", "ETHUSDT"]) {
    for (const interval of ["15", "60", "240", "D"]) {
      const snapshot = await request.get(`/api/market?symbol=${symbol}&interval=${interval}`);
      expect(snapshot.ok()).toBeTruthy();
      const market = await snapshot.json();
      expect(market.symbol).toBe(symbol);
      expect(market.interval).toBe(interval);
      expect(Number(market.ticker.price)).toBeGreaterThan(0);
      expect(market.stale).toBe(false);
      expect(market.indicators.closed_candles).toBeGreaterThanOrEqual(299);
    }
  }
  expect((await request.get("/api/market?symbol=SOLUSDT")).status()).toBe(400);
  expect((await request.post("/api/market")).status()).toBe(405);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("Dados atualizados", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /de candles de BTCUSDT/ })).toBeVisible();
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.screenshot({ path: `artifacts/dashboard-${testInfo.project.name}.png`, fullPage: true });
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
