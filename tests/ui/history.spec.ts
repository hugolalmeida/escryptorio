import { expect, test, type Page } from "@playwright/test";

// Dados sintéticos exclusivamente para testes da interface; não são fallback do produto.
const id = "b".repeat(64);
const jobId = "a".repeat(32);
const start = Date.parse("2026-09-01T00:00:00Z")/1000;
const end = Date.parse("2026-11-01T00:00:00Z")/1000;
const manifest = { dataset_id: id, sha256: id, schema_version: 1, source: "Bybit", market: "spot", symbol: "BTCUSDT",
  interval: "60", start_time: start, end_time: end, candle_count: 1464, gaps: [], coverage_ratio: 1,
  integrity_status: "approved", approved_at_ms: 1793570000000, first_collected_at_ms: 1793570000000,
  last_collected_at_ms: 1793570000000, collector_version: "bybit-v5-history/1", pybit_version: "5.17.0" };
const initialJob = { id: jobId, symbol: "BTCUSDT", interval: "60", start_time: start, end_time: end,
  status: "incomplete", stored_count: 1463, expected_count: 1464, pages: 2, cancel_requested: 0,
  error_code: "MISSING_CANDLES", dataset_id: null, updated_at_ms: 1793570000000,
  runs: [{ id: 1, status: "incomplete", error_code: "MISSING_CANDLES" }],
  gaps: [{ start_time: start+3600, end_time: start+7200, candle_count: 1 }] };

async function mockHistory(page: Page, { empty = false, verifyError = false } = {}) {
  let jobs = empty ? [] : [{ ...initialJob }];
  const submitted: unknown[] = [];
  await page.route("**/api/history/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (request.method() === "POST") {
      expect(request.headers()["x-cryptolab-research"]).toBe("1");
      if (path.endsWith("/jobs")) {
        submitted.push(request.postDataJSON());
        jobs = [{ ...initialJob, status: "queued", stored_count: 0, pages: 0, error_code: null! }];
      } else if (path.endsWith("/resume")) jobs = jobs.map(job => ({ ...job, status: "queued", error_code: null! }));
      else if (path.endsWith("/pause")) jobs = jobs.map(job => ({ ...job, status: "paused" }));
      return route.fulfill({ status: 202, json: jobs[0] });
    }
    if (path.endsWith("/jobs")) return route.fulfill({ json: { jobs } });
    if (path.endsWith("/datasets")) return route.fulfill({ json: { datasets: empty ? [] : [manifest] } });
    if (path.endsWith(`/datasets/${id}`)) {
      if (verifyError) return route.fulfill({ status: 409, json: { detail: "Dataset recusado: hash inválido." } });
      return route.fulfill({ json: { manifest, reference_hash: id, total_count: 1464,
        candles: Array.from({ length: 3 }, (_, i) => ({ time: start+i*3600, open: "100", high: "102", low: "99", close: "101", volume: "1.00000001", turnover: "101", closed: true })) } });
    }
    return route.fulfill({ json: { source: "Bybit", market: "spot", symbol: "BTCUSDT", interval: "60",
      start_time: start, end_time: end, stored_count: empty ? 0 : 1463, expected_count: 1464,
      coverage_ratio: empty ? 0 : 1463/1464, complete: false,
      segments: [], gaps: empty ? [{ start_time: start, end_time: end, candle_count: 1464 }] : initialJob.gaps } });
  });
  return submitted;
}

test("histórico: formulário UTC, fila e estado vazio sem dados fictícios", async ({ page }) => {
  const submitted = await mockHistory(page, { empty: true });
  await page.goto("/history");
  await expect(page.getByRole("heading", { name: "Pesquisa histórica" })).toBeVisible();
  await expect(page.getByText("Nenhuma coleta solicitada", { exact: true })).toBeVisible();
  await expect(page.getByText("Nenhum dataset aprovado", { exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Ativo", exact: true }).selectOption("ETHUSDT");
  await page.getByRole("combobox", { name: "Timeframe", exact: true }).selectOption("15");
  await page.getByLabel("Início UTC · inclusivo").fill("2026-10-01T00:00");
  await page.getByLabel("Fim UTC · exclusivo").fill("2026-11-01T00:00");
  await page.getByRole("button", { name: "Solicitar coleta", exact: true }).click();
  await expect(page.getByText("Na fila", { exact: true })).toBeVisible();
  expect(submitted).toEqual([{ symbol: "ETHUSDT", interval: "15", start: "2026-10-01T00:00:00Z", end: "2026-11-01T00:00:00Z" }]);
  await expect(page.getByRole("status")).toContainText("Solicitação persistida");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("histórico: lacunas, retomada e pausa preservam progresso", async ({ page }) => {
  await mockHistory(page);
  await page.goto("/history");
  await expect(page.getByText("MISSING_CANDLES", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Cobertura do período" })).toContainText("Faixas ausentes");
  await page.getByRole("button", { name: "Retomar", exact: true }).click();
  await expect(page.getByText("Na fila", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Pausar", exact: true }).click();
  await expect(page.getByText("Pausada", { exact: true })).toBeVisible();
  await expect(page.locator(".history-jobs").getByText("1.463 / 1.464", { exact: true })).toBeVisible();
});

test("histórico: verifica dataset e apresenta hash completo e OHLCV", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await mockHistory(page);
  await page.goto("/history");
  await page.getByRole("button", { name: "Verificar e consultar" }).click();
  await expect(page.getByText(/Hash verificado · 1.464 candles disponíveis/)).toBeVisible();
  await expect(page.getByText(id, { exact: true })).toBeVisible();
  await expect(page.getByRole("caption")).toContainText("Prévia dos primeiros 3 candles");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
});

test("histórico: recusa dataset com hash inválido e período desalinhado", async ({ page }) => {
  await mockHistory(page, { verifyError: true });
  await page.goto("/history");
  await page.getByRole("button", { name: "Verificar e consultar" }).click();
  await expect(page.getByRole("alert", { name: "Erro na pesquisa" })).toContainText("hash inválido");
  await expect(page.getByText(/Hash verificado/)).toHaveCount(0);
  await page.getByRole("combobox", { name: "Timeframe", exact: true }).selectOption("60");
  await page.getByLabel("Início UTC · inclusivo").fill("2026-10-01T00:15");
  await expect(page.getByRole("button", { name: "Solicitar coleta", exact: true })).toBeDisabled();
});

test("histórico: backend ausente tem erro recuperável", async ({ page }) => {
  await page.route("**/api/history/**", route => route.fulfill({ status: 503, json: { detail: "Backend local indisponível." } }));
  await page.goto("/history");
  await expect(page.getByRole("alert", { name: "Erro na pesquisa" })).toContainText("Backend local indisponível");
  await expect(page.getByRole("button", { name: "Atualizar", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("histórico real: catálogo, cobertura e consulta offline", async ({ page, request }, testInfo) => {
  test.skip(process.env.CRYPTOLAB_HISTORY_SMOKE !== "1", "Requer backfill real e API local; separado dos mocks.");
  const coverageResponse = await request.get("/api/history/coverage?symbol=BTCUSDT&interval=60&start=2026-09-01&end=2026-11-01");
  expect(coverageResponse.ok()).toBeTruthy();
  const coverage = await coverageResponse.json();
  expect(coverage.stored_count).toBe(1464);
  expect(coverage.complete).toBe(true);
  const response = await request.get("/api/history/datasets");
  const dataset = (await response.json()).datasets.find((d: typeof manifest) => d.symbol === "BTCUSDT" && d.interval === "60" && d.start_time === start && d.end_time === end);
  expect(dataset).toBeTruthy();
  const verified = await request.get(`/api/history/datasets/${dataset.dataset_id}?limit=3`);
  expect(verified.ok()).toBeTruthy();
  expect((await verified.json()).reference_hash).toBe(dataset.dataset_id);
  expect((await request.post("/api/history/jobs", { data: {} })).status()).toBe(403);
  expect((await request.get("/api/history/private-orders")).status()).toBe(404);
  const enqueued = await request.post("/api/history/jobs", { headers: { "X-CryptoLab-Research": "1" },
    data: { symbol: "BTCUSDT", interval: "60", start: "2026-09-01", end: "2026-09-02" } });
  expect(enqueued.status()).toBe(202);
  const queued = await enqueued.json();
  await expect.poll(async () => (await (await request.get(`/api/history/jobs/${queued.id}`)).json()).status,
    { timeout: 15000 }).toBe("completed");
  const completed = await (await request.get(`/api/history/jobs/${queued.id}`)).json();
  expect(completed.stored_count).toBe(24);
  expect(completed.pages).toBe(0); // fila → worker → aprovação a partir do arquivo, sem rede nova
  await page.goto("/history");
  await page.getByLabel("Início UTC · inclusivo").fill("2026-09-01T00:00");
  await page.getByLabel("Fim UTC · exclusivo").fill("2026-11-01T00:00");
  await expect(page.getByRole("region", { name: "Cobertura do período" })).toContainText("Completa");
  await page.screenshot({ path: `artifacts/history-${testInfo.project.name}.png`, fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
