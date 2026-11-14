import { expect, test } from "@playwright/test";

// Dados sintéticos isolados, nunca usados como fallback do produto.
const envelope = (data: unknown) => ({ schema_version: 1, observed_at_ms: Date.now(), data });
const wallet = { wallet_id: "a".repeat(32), wallet_hash: "b".repeat(64), head_hash: "c".repeat(64), sequence: 1, ledger_version: "test", spec: { bot_id: "bot-teste", strategy: "trend", symbol: "BTCUSDT", interval: "60", initial_capital: "1000" }, state: { cash: "1000", quantity: "0", acquisition_cost: "0", realized_pnl: "0", total_fees: "0", state: "paused" }, mark_status: "UNAVAILABLE", mark_price: null, mark_source_time_ms: null, average_cost: null, position_value: "0", exposure: "0", equity: "1000", unrealized_pnl: "0", total_pnl: "0", last_event_time: 1 };
const overview = { summary: {initial_capital:"1000",cash:"1000",equity:"1000",position_value:"0",realized_pnl:"0",unrealized_pnl:"0",total_pnl:"0",wallets:1,positions:0,fills:0,decisions:0,integrity:"WALLETS_VERIFIED"}, wallets:[wallet],markets:[],collection:null,monitor_status:"UNKNOWN" };
const operational = {schema_version:1,observed_at_ms:Date.now(),process_liveness:"UNKNOWN",financial_integrity:"DEGRADED",collection:null,markets:[{symbol:"BTCUSDT",interval:"60",status:"STALE",source_time_ms:1,fetched_at_ms:2,age_ms:999,stale_after_seconds:90,dataset_id:null}],monitors:[],wallets:[],decisions:[],truncated:false,alerts:[
  {id:"critical",code:"PAPER_LEDGER_INTEGRITY_FAILED",severity:"CRITICAL",component:"wallet",resource_id:"fixture",observed_at_ms:1,source_time_ms:null,first_seen_at_ms:null,reason:"Ledger inconsistente.",evidence:{},suggested_action:"Inspecione a base."},
  {id:"info",code:"MONITOR_STATUS_UNKNOWN",severity:"INFO",component:"monitor",resource_id:"process",observed_at_ms:1,source_time_ms:null,first_seen_at_ms:null,reason:"Sem heartbeat.",evidence:{},suggested_action:"Verifique o processo."}]};

test("central operacional mostra evidência, filtros e liveness desconhecida", async ({page}) => {
  const writes: string[] = [];
  page.on("request",r=>{if(r.url().includes("/api/paper/") && r.method() !== "GET") writes.push(r.method());});
  await page.route("**/api/paper/**", route => {
    const path = new URL(route.request().url()).pathname;
    const value = path.endsWith("operations/overview") ? operational : path.endsWith("overview") ? overview : [];
    return route.fulfill({json:envelope(value)});
  });
  await page.goto("/paper");
  await expect(page.getByRole("heading",{name:"Central de operações"})).toBeVisible();
  await expect(page.getByText("UNKNOWN · sem heartbeat contínuo")).toBeVisible();
  await expect(page.getByText(/CRITICAL · PAPER_LEDGER/)).toBeVisible();
  await expect(page.getByLabel("Resumo financeiro fictício")).toHaveCount(0);
  await page.getByText(/CRITICAL · PAPER_LEDGER/).click();
  await expect(page.getByText("Ledger inconsistente.")).toBeVisible();
  await page.getByLabel("Severidade").selectOption("INFO");
  await expect(page.getByText(/INFO · MONITOR_STATUS_UNKNOWN/)).toBeVisible();
  await expect(page.getByText(/1 críticas, incluindo as ocultas/)).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  expect(writes).toEqual([]);
});

test("carteira indisponível permanece na tabela; sinais e decisões são independentes", async ({page}) => {
  await page.route("**/api/paper/**", route => {
    const path = new URL(route.request().url()).pathname;
    if(path.endsWith("signals") || path.endsWith(wallet.wallet_id)) return route.fulfill({status:503,json:{}});
    const value = path.endsWith("operations/overview") ? {...operational, financial_integrity:"PARTIAL_VERIFIED", alerts:[]} : path.endsWith("overview") ? overview : path.endsWith("decisions") ? [] : path.endsWith("equity") ? {items:[]} : {items:[],total:0,offset:0,limit:10};
    return route.fulfill({json:envelope(value)});
  });
  await page.goto("/paper");
  await expect(page.getByText("Sinais indisponíveis.")).toBeVisible();
  await expect(page.getByText("Nenhuma decisão registrada.")).toBeVisible();
  await page.getByRole("button",{name:"Ver carteira"}).click();
  await expect(page.getByRole("row").filter({hasText:"bot-teste"})).toContainText("Indisponível");
  await expect(page.getByText("Você ainda não possui carteiras virtuais registradas.")).toHaveCount(0);
  await expect(page.getByRole("button",{name:/^(BUY|SELL)$/i})).toHaveCount(0);
});

test("decisões indisponíveis não escondem sinais", async ({page}) => {
  const signal = {id:"a".repeat(64),definition:{config:{bot_id:"bot-sinal",strategy:"trend",symbol:"BTCUSDT",interval:"60"}},config_hash:"b".repeat(64),dataset_id:"c".repeat(64),candle_time:1,decision_time:2,valid_until:3,origin:"current",temporal_status:"EXPIRED",if_flat:{action:"hold"},if_long:{action:"sell"}};
  await page.route("**/api/paper/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("decisions")) return route.fulfill({status:503,json:{}});
    const value = path.endsWith("operations/overview") ? {...operational,financial_integrity:"PARTIAL_VERIFIED",alerts:[]} : path.endsWith("overview") ? overview : path.endsWith("signals") ? [signal] : [];
    return route.fulfill({json:envelope(value)});
  });
  await page.goto("/paper");
  await expect(page.getByText("Decisões indisponíveis.")).toBeVisible();
  await expect(page.getByRole("row").filter({hasText:"bot-sinal"})).toBeVisible();
});
