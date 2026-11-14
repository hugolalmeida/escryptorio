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
  await expect(page.getByRole("alert").filter({ hasText: "Resumo: consulta indisponível" })).toContainText("integridade não pôde ser verificada");
  await expect(page.getByText("1000 USDT")).toHaveCount(0);
});

test("paper: falha de detalhes não é apagada pelo resumo e recuperação não usa dados antigos", async ({ page }) => {
  let fail = true;
  await page.route("**/api/paper/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith(wallet.wallet_id) && fail) return route.fulfill({ status: 503, json: {} });
    const data = path.endsWith("overview") ? { summary, wallets: [wallet], markets: [], collection: null, monitor_status: "UNKNOWN" }
      : path.endsWith("signals") || path.endsWith("decisions") ? [] : path.endsWith("fills") || path.endsWith("events") ? { items: [], total: 0, offset: 0, limit: 10 }
      : path.endsWith("equity") ? { items: [] } : { ...wallet, mark_status: "FRESH", mark_price: "150", equity: "1049", unrealized_pnl: "49" };
    return route.fulfill({ json: envelope(data) });
  });
  await page.goto("/paper");
  await page.getByRole("button", { name: "Ver carteira" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Carteira: consulta indisponível" })).toBeVisible();
  await expect(page.getByText("Integridade da carteira selecionada: desconhecida")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Detalhe/ })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Fills virtuais" })).toHaveCount(0);
  fail = false;
  await page.getByRole("button", { name: "Atualizar" }).click();
  await expect(page.getByRole("heading", { name: /Detalhe/ })).toBeVisible();
  await expect(page.getByText("1049 USDT")).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Carteira:" })).toHaveCount(0);
});

test("paper: troca rápida impede resposta anterior de substituir carteira atual", async ({ page }) => {
  const second = { ...wallet, wallet_id: "d".repeat(32), spec: { ...wallet.spec, bot_id: "bot-segundo" } };
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let entered!: () => void;
  const firstRequested = new Promise<void>(resolve => { entered = resolve; });
  await page.route("**/api/paper/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith(wallet.wallet_id)) { entered(); await gate; }
    const data = path.endsWith("overview") ? { summary, wallets: [wallet,second], markets: [], collection: null, monitor_status: "UNKNOWN" }
      : path.endsWith("signals") || path.endsWith("decisions") ? [] : path.endsWith("fills") || path.endsWith("events") ? { items: [], total: 0, offset: 0, limit: 10 }
      : path.endsWith("equity") ? { items: [] } : path.endsWith(second.wallet_id) ? second : wallet;
    try { await route.fulfill({ json: envelope(data) }); } catch { /* request cancelled on selection */ }
  });
  await page.goto("/paper");
  await page.getByRole("row").filter({ hasText: "bot-fixture" }).getByRole("button", { name: "Ver carteira" }).click();
  await firstRequested;
  await page.getByRole("row").filter({ hasText: "bot-segundo" }).getByRole("button", { name: "Ver carteira" }).click();
  await expect(page.getByRole("heading", { name: "Detalhe · bot-segundo" })).toBeVisible();
  release();
  await expect(page.getByRole("heading", { name: "Detalhe · bot-fixture" })).toHaveCount(0);
});

test("paper: refresh concorrente mantém resposta mais recente", async ({ page }) => {
  let release!: () => void;
  let entered!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const requested = new Promise<void>(resolve => { entered = resolve; });
  let count = 0;
  await page.route("**/api/paper/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("overview")) {
      count++;
      const current = count;
      if (current === 1) { entered(); await gate; }
      const data = { summary: { ...summary, cash: current === 1 ? "111" : "222" }, wallets: [], markets: [], collection: null, monitor_status: "UNKNOWN" };
      try { await route.fulfill({ json: envelope(data) }); } catch { /* cancelled stale request */ }
      return;
    }
    await route.fulfill({ json: envelope([]) });
  });
  await page.goto("/paper");
  await requested;
  await page.getByRole("button", { name: "Atualizar" }).click();
  await expect(page.getByText("222 USDT")).toBeVisible();
  release();
  await expect(page.getByText("111 USDT")).toHaveCount(0);
});
