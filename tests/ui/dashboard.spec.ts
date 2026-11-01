import { expect, test, type Page } from "@playwright/test";

// Fixtures sintéticas exclusivamente de teste. Nunca importadas pelo aplicativo.
function fixture(symbol: string, interval: string, stale = false) {
  const sourceTime = Date.now() - (stale ? 120000 : 0);
  const step = (interval === "D" ? 86400 : Number(interval) * 60);
  const start = Math.floor(sourceTime / 1000 / step) * step - step * 79;
  const base = symbol === "BTCUSDT" ? 70000 : 2500;
  const candles = Array.from({ length: 80 }, (_, i) => {
    const value = base + i * 5 + Math.sin(i) * 12;
    return { time: start + i * step, open: String(value), high: String(value + 20), low: String(value - 20),
      close: String(value + 8), volume: String(10 + i), turnover: String(value * (10 + i)), closed: i < 79 };
  });
  return { symbol, interval, category: "spot", source: "Bybit", source_time_ms: sourceTime, fetched_at_ms: sourceTime,
    served_at_ms: Date.now(), stale, stale_after_seconds: 90, dataset_id: "a".repeat(64), live_trading_enabled: false,
    ticker: { price: String(base), change_24h: "0.0125", high_24h: String(base + 1000), low_24h: String(base - 1000),
      volume_24h: "10000", turnover_24h: "50000000", source_time_ms: sourceTime }, candles,
    indicators: { sma_20: candles.slice(19, -1).map(c => ({ time: c.time, value: String(Number(c.close) - 45) })),
      ema_50: candles.slice(49, -1).map(c => ({ time: c.time, value: String(Number(c.close) - 110) })),
      rsi_14: "62.14", atr_14: "40", trend: "alta", closed_candles: 79, as_of: candles[78].time }, instrument: {} };
}

async function mockMarket(page: Page, stale = false) {
  await page.route("**/api/market?*", async route => {
    const url = new URL(route.request().url());
    await route.fulfill({ json: fixture(url.searchParams.get("symbol")!, url.searchParams.get("interval")!, stale) });
  });
}

test("dashboard: dados, gráfico, ativo, período e controles", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await mockMarket(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Visão de mercado" })).toBeVisible();
  await expect(page.getByText("Dados atualizados", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /de candles de BTCUSDT/ })).toBeVisible();
  await expect(page.getByText("62,14", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Ethereum/ }).click();
  await expect(page.getByRole("img", { name: /de candles de ETHUSDT/ })).toBeVisible();
  await page.getByRole("button", { name: "4h", exact: true }).click();
  await expect(page.getByRole("button", { name: "4h", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Exibir linha" }).click();
  await expect(page.getByRole("img", { name: /de linha de ETHUSDT/ })).toBeVisible();
  await page.getByRole("button", { name: "Médias", exact: true }).click();
  await expect(page.getByRole("button", { name: "Médias", exact: true })).toHaveAttribute("aria-pressed", "false");
  await page.getByRole("button", { name: "Atualizar", exact: true }).click();
  await expect(page.getByText("Dados atualizados", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
});

test("API indisponível: erro explícito, sem preços inventados", async ({ page }) => {
  await page.route("**/api/market?*", route => route.fulfill({ status: 503, json: { detail: "Worker indisponível no teste." } }));
  await page.goto("/");
  await expect(page.getByRole("alert", { name: "Atualização de mercado" })).toContainText("Atualização interrompida");
  await expect(page.getByText("Sem dados de mercado", { exact: true })).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test("snapshot obsoleto: avisa e não apresenta tendência acionável", async ({ page }) => {
  await mockMarket(page, true);
  await page.goto("/");
  await expect(page.getByText("A coleta precisa ser atualizada", { exact: true })).toBeVisible();
  await expect(page.getByText("Tendência de alta", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Dados obsoletos", { exact: true })).toHaveCount(2);
});

test("falha depois de sucesso preserva snapshot e horário", async ({ page }) => {
  await mockMarket(page);
  await page.goto("/");
  await expect(page.getByText("Dados atualizados", { exact: true })).toBeVisible();
  const timestamp = await page.locator(".provenance dd").first().textContent();
  await page.unroute("**/api/market?*");
  await page.route("**/api/market?*", route => route.fulfill({ status: 503, json: { detail: "Falha de rede de teste." } }));
  await page.getByRole("button", { name: "Atualizar", exact: true }).click();
  await expect(page.getByRole("alert", { name: "Atualização de mercado" })).toContainText("horário original");
  await expect(page.locator(".provenance dd").first()).toHaveText(timestamp!);
  await expect(page.getByRole("img", { name: /de candles de BTCUSDT/ })).toBeVisible();
});

test("navegação e bloqueio de execução", async ({ page }, testInfo) => {
  await mockMarket(page);
  await page.goto("/");
  if (testInfo.project.name === "mobile") await page.getByRole("button", { name: "Abrir menu" }).click();
  await page.getByRole("link", { name: "Execução real", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Execução real desativada" })).toBeVisible();
  await expect(page.getByText(/LIVE_TRADING_ENABLED=false/)).toBeVisible();
  await expect(page.getByRole("button", { name: /comprar|vender|executar|ativar/i })).toHaveCount(0);
  await page.getByRole("link", { name: "Voltar ao dashboard" }).click();
  await page.getByRole("link", { name: "Explorar Arena" }).click();
  await expect(page.getByRole("heading", { name: "Arena", exact: true })).toBeVisible();
  await expect(page.getByText(/Mack reservada como não validada/)).toBeVisible();
});

test("teclado: pular navegação e fechar menu com Escape", async ({ page }, testInfo) => {
  await mockMarket(page);
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Pular para o conteúdo" })).toBeFocused();
  await page.keyboard.press("Enter");
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Abrir menu" }).click();
    await expect(page.getByRole("link", { name: "Carteira Bybit" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Abrir menu" })).toBeFocused();
    await expect(page.getByRole("link", { name: "Carteira Bybit" })).not.toBeVisible();
  }
});
