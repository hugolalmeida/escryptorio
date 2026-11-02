import { expect, test, type Page } from "@playwright/test";

// Fixtures sintéticas exclusivas da suíte; aplicação não tem fallback de demonstração.
const dataset = "b".repeat(64), protocol = "c".repeat(64), run = "d".repeat(64);
const start = Date.parse("2026-09-01T00:00:00Z")/1000;
const manifest = { dataset_id: dataset, symbol: "BTCUSDT", interval: "60", candle_count: 1464, start_time: start, end_time: start+1464*3600 };
const metrics = { net_return_pct:"1.25",pnl:"125",final_equity:"10125",max_drawdown_pct:"2",win_rate_pct:null,profit_factor:null,expectancy:null,closed_trades:0,wins:0,losses:0,breakeven:0,realized_win_loss_ratio:null,fees:"5",slippage_cost:"2",total_costs:"7",exposure_pct:"50",undefined:{profit_factor:"Sem perdas realizadas; denominador zero"} };
const simulation = { metrics, equity:[{time:start,equity:"10000",cash:"10000",quantity:"0",drawdown_pct:"0"},{time:start+3600,equity:"10125",cash:"10125",quantity:"0",drawdown_pct:"0"}],trades:[],fills:[],plans:[],rejections:[],portfolio:{cash:"10125",position:null} };
const result = { id:run,manifest:{dataset_hash:dataset,symbol:"BTCUSDT",interval:"60",strategy:"trend",strategy_version:"1",start_time:start,end_time:start+7200,protocol_id:protocol,partition:"train",config:{capital:"10000",final_policy:"liquidate"},engine_version:"synthetic-test",code_commit:"synthetic"},simulation,benchmark:simulation,excess_return_pp:"0",warnings:["Amostra insuficiente: fixture sintética de teste."] };

async function mock(page: Page, empty=false, fail=false) {
  const submissions: Record<string,unknown>[] = [];
  await page.route("**/api/history/datasets", r => r.fulfill({json:{datasets:empty ? [] : [manifest]}}));
  await page.route("**/api/research/**", r => {
    const req = r.request(), path = new URL(req.url()).pathname;
    if (req.method() === "POST") {
      expect(req.headers()["x-cryptolab-research"]).toBe("1");
      if (fail) return r.fulfill({status:409,json:{detail:"INSUFFICIENT_WARMUP: reserve histórico anterior"}});
      if (path.endsWith("protocols")) { submissions.push(req.postDataJSON()); return r.fulfill({json:{id:protocol}}); }
      if (path.endsWith("verify")) return r.fulfill({json:{identical:true}});
      return r.fulfill({json:result});
    }
    return r.fulfill({json:path.endsWith("runs") ? {runs:[]} : result});
  });
  return submissions;
}

test("backtest: configurar, congelar, executar, consultar gráfico e reproduzir", async ({page}) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  const submitted = await mock(page);
  await page.goto("/backtesting");
  await page.getByRole("combobox",{name:"Dataset aprovado"}).selectOption(dataset);
  await page.getByRole("button",{name:"Congelar protocolo"}).click();
  await expect(page.getByRole("combobox",{name:"Estratégia",exact:true})).toBeDisabled();
  expect(submitted[0].strategy).toBe("trend");
  expect((submitted[0].config as {capital:string}).capital).toBe("10000");
  await page.getByRole("button",{name:"Executar backtest"}).click();
  await expect(page.getByRole("heading",{name:"Resultado · Trend Following"})).toBeVisible();
  await expect(page.getByRole("img",{name:/Patrimônio simulado/})).toBeVisible();
  await expect(page.getByText("Nenhum trade encerrado",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Verificar hash"}).click();
  await expect(page.getByRole("status").filter({hasText:"Reexecução idêntica"})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test("backtest: estados vazios, ativo, estratégia e ausência de fallback", async ({page}) => {
  await mock(page,true);
  await page.goto("/backtesting");
  await expect(page.getByText("Nenhum dataset aprovado para esta seleção.",{exact:false})).toBeVisible();
  await expect(page.getByRole("button",{name:"Congelar protocolo"})).toBeDisabled();
  await page.getByRole("combobox",{name:"Ativo",exact:true}).selectOption("ETHUSDT");
  await page.getByRole("combobox",{name:"Estratégia",exact:true}).selectOption("rsi");
  await expect(page.getByLabel("RSI de recuperação",{exact:true})).toBeVisible();
  await page.getByRole("combobox",{name:"Estratégia",exact:true}).selectOption("breakout");
  await expect(page.getByLabel("Candles de resistência",{exact:true})).toBeVisible();
  await page.getByRole("combobox",{name:"Estratégia",exact:true}).selectOption("buy_hold");
  await expect(page.getByLabel("Risco planejado (fração)",{exact:true})).toBeDisabled();
  await expect(page.getByText("Nenhum resultado selecionado",{exact:true})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("backtest: erro de warm-up preserva configuração e permite corrigir", async ({page}) => {
  await mock(page,false,true);
  await page.goto("/backtesting");
  await page.getByRole("combobox",{name:"Dataset aprovado"}).selectOption(dataset);
  await page.getByRole("button",{name:"Congelar protocolo"}).click();
  await expect(page.getByRole("alert").filter({hasText:"Pesquisa interrompida"})).toContainText("INSUFFICIENT_WARMUP");
  await expect(page.getByRole("combobox",{name:"Dataset aprovado"})).toHaveValue(dataset);
  await expect(page.getByRole("button",{name:"Congelar protocolo"})).toBeEnabled();
});

test("backtest: falha de API visível sem números fabricados", async ({page}) => {
  await page.route("**/api/**", r => r.fulfill({status:503,json:{detail:"Backend indisponível"}}));
  await page.goto("/backtesting");
  await expect(page.getByRole("alert").filter({hasText:"Pesquisa interrompida"})).toContainText("Backend indisponível");
  await expect(page.getByRole("button",{name:"Congelar protocolo"})).toBeDisabled();
  await expect(page.getByRole("heading",{name:/Resultado ·/})).toHaveCount(0);
});

test("backtest real: reader aprovado → protocolo → replay → hash e interface", async ({page, request}, info) => {
  test.skip(process.env.CRYPTOLAB_BACKTEST_SMOKE !== "1","Requer API e dataset local aprovado; nenhum download automático");
  test.setTimeout(90000);
  const real = "f3b2e55b1cc373d448efa3676c63064cb482c86be4ebd7442bce573134f972c6";
  await page.goto("/backtesting");
  await page.getByRole("combobox",{name:"Dataset aprovado"}).selectOption(real);
  await page.getByRole("button",{name:"Congelar protocolo"}).click();
  await expect(page.getByRole("button",{name:"Executar backtest"})).toBeVisible({timeout:15000});
  await page.getByRole("button",{name:"Executar backtest"}).click();
  await expect(page.getByRole("heading",{name:"Resultado · Trend Following"})).toBeVisible({timeout:60000});
  await page.getByRole("button",{name:"Verificar hash"}).click();
  await expect(page.getByRole("status").filter({hasText:"Reexecução idêntica"})).toBeVisible({timeout:60000});
  await expect(page.getByRole("img",{name:/Patrimônio simulado/})).toBeVisible();
  const idText = await page.locator(".history-full-hash").filter({hasText:"Execução "}).first().textContent();
  const id = idText!.replace("Execução ", "").trim();
  await page.reload();
  await page.getByRole("row").filter({hasText:id.slice(0,16)}).getByRole("button",{name:"Retomar protocolo"}).click();
  await expect(page.getByRole("status").filter({hasText:"Protocolo anterior restaurado"})).toBeVisible();
  await page.getByRole("combobox",{name:"Janela",exact:true}).selectOption("validation");
  await page.getByRole("button",{name:"Executar backtest"}).click();
  await expect(page.getByText(/Resultado · Trend Following/)).toBeVisible();
  await expect(page.getByText(/BTCUSDT · Validação/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("heading",{name:"Resultado · Trend Following"}).scrollIntoViewIfNeeded();
  await page.screenshot({path:`artifacts/backtest-${info.project.name}.png`,fullPage:true});
  expect((await request.post("/api/research/orders",{data:{}})).status()).toBe(404);
  expect((await request.post("/api/research/runs",{data:{},headers:{Origin:"https://evil.invalid","X-CryptoLab-Research":"1"}})).status()).toBe(403);
});
