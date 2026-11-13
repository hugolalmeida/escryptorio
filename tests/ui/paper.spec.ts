import { expect, test } from "@playwright/test";

// Fixture sintética, interceptada no navegador; não integra a aplicação.
const envelope = (data: unknown) => ({ schema_version: 1, observed_at_ms: Date.now(), data });
const wallet = { wallet_id: "a".repeat(32), wallet_hash: "b".repeat(64), head_hash: "c".repeat(64), sequence: 2, ledger_version: "test/1", spec: { bot_id: "bot-fixture", strategy: "trend", symbol: "BTCUSDT", interval: "60", initial_capital: "1000" }, state: { cash: "899", quantity: "1", acquisition_cost: "101", realized_pnl: "0", total_fees: "1", state: "paused" }, mark_status: "STALE", mark_price: null, mark_source_time_ms: null, average_cost: "101", position_value: null, exposure: null, equity: null, unrealized_pnl: null, total_pnl: null, last_event_time: 1, binding: null };
const summary = { initial_capital: "1000", cash: "899", equity: null, position_value: null, realized_pnl: "0", unrealized_pnl: null, total_pnl: null, wallets: 1, positions: 1, fills: 1, decisions: 0, integrity: "WALLETS_VERIFIED" };

test("paper: estados, filtros, detalhe e leitura sem mutações", async ({ page }) => {
  const writes: string[] = [];
  page.on("request", request => { if (request.url().includes("/api/paper/") && request.method() !== "GET") writes.push(request.method()); });
  await page.route("**/api/paper/**", async route => {
    const path = new URL(route.request().url()).pathname;
    const data = path.endsWith("overview") ? { summary, wallets: [wallet], markets: [{ symbol: "BTCUSDT", status: "STALE", source_time_ms: 1 }], collection: null, monitor_status: "UNKNOWN" }
      : path.endsWith("signals") || path.endsWith("decisions") ? [] : path.endsWith("fills") ? { items: [], total: 0, offset: 0, limit: 10 }
      : path.endsWith("events") ? { items: [], total: 0, offset: 0, limit: 10 } : path.endsWith("equity") ? { items: [] } : wallet;
    await route.fulfill({ json: envelope(data) });
  });
  await page.goto("/paper");
  await expect(page.getByText("PAPER TRADING — SALDOS FICTÍCIOS")).toBeVisible();
  await expect(page.getByText("Obsoleto", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("Pausada", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Ver carteira" }).click();
  await expect(page.getByRole("heading", { name: /Detalhe/ })).toBeVisible();
  await expect(page.getByText("Dados insuficientes para uma curva de patrimônio válida.")).toBeVisible();
  await expect(page.getByText("Nenhuma operação fictícia nesta página.")).toBeVisible();
  await page.getByLabel("Buscar carteira").fill("inexistente");
  await expect(page.getByText("Você ainda não possui carteiras virtuais registradas.")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await expect(page.getByRole("button", { name: /^(BUY|SELL)$/i })).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("paper: falha do backend não apresenta valores antigos", async ({ page }) => {
  await page.route("**/api/paper/**", route => route.fulfill({ status: 503, json: { detail: "indisponível" } }));
  await page.goto("/paper");
  await expect(page.getByRole("alert").filter({ hasText: "Consulta indisponível" })).toContainText("integridade não pôde ser verificada");
  await expect(page.getByText("1000 USDT")).toHaveCount(0);
});
