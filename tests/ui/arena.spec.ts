import { expect, test, type Page } from "@playwright/test";

// Fixtures sintéticas, exclusivas dos testes: a aplicação não fornece fallback.
const datasetId = "a".repeat(64), experimentId = "b".repeat(64), resultId = "c".repeat(64);
const start = Date.parse("2026-09-01T00:00:00Z")/1000;
const dataset = {dataset_id:datasetId,symbol:"BTCUSDT",interval:"60",candle_count:1000,start_time:start,end_time:start+1000*3600};
const names = ["trend","rsi","breakout","buy_hold"] as const;
type Bot = typeof names[number];
const phases = ["train","validation","test"] as const;
type Phase = typeof phases[number];
const runId = (p:Phase,bot:Bot) => (String(1+phases.indexOf(p)*4+names.indexOf(bot))).padStart(64,"0");
const ids = Object.fromEntries(names.map((id,i) => [id,String(i+1).repeat(64)]));
const entry = (bot:Bot,p:Phase,i:number) => ({strategy:bot,strategy_version:"1",parameters:{},protocol_id:ids[bot],run_id:runId(p,bot),
  net_return_pct:i<2 ? "1.00000001" : String(-i),max_drawdown_pct:"2.5",profit_factor:i === 0 ? null : "1.5",win_rate_pct:i === 0 ? null : "50",
  closed_trades:i,total_costs:"3",exposure_pct:"30",excess_return_pp:"2",expectancy:i === 0 ? null : "1.5",
  undefined:i === 0 ? {profit_factor:"Sem perdas realizadas",win_rate_pct:"Sem trades encerrados",expectancy:"Sem trades encerrados"} : {},insufficient_sample:true,rank:i<2 ? 1 : i+1});

async function mocks(page:Page, options:{empty?:boolean; createError?:number; executeError?:number; malformed?:boolean; recoverBusy?:boolean; recoverFound?:boolean} = {}) {
  let created: Record<string,unknown> | undefined;
  let persisted = false;
  let resultChecks = 0;
  let posts = 0;
  const protocolIds = ids as Record<Bot,string>;
  const result = () => {
    const c = created as {train_start:number;train_end:number;validation_end:number;test_end:number};
    const windows:Record<Phase,[number,number]> = {train:[c.train_start,c.train_end],validation:[c.train_end,c.validation_end],test:[c.validation_end,c.test_end]};
    return {id:resultId,experiment_id:experimentId,arena_version:"synthetic-test",run_ids:Object.fromEntries(phases.map(p => [p,Object.fromEntries(names.map(bot => [bot,runId(p,bot)]))])),
      rankings:Object.fromEntries(phases.map(p => [p,{start_time:windows[p][0],end_time:windows[p][1],out_of_sample:p === "test",entries:names.map((bot,i) => entry(bot,p,i)),insufficient_sample:true,validated_winner:null}])),warnings:["Fixture sintética para testes"]};
  };
  await page.route("**/api/history/datasets", r => r.fulfill({json:{datasets:options.empty ? [] : [dataset]}}));
  await page.route("**/api/arena/**", r => {
    const req=r.request(), path=new URL(req.url()).pathname;
    if (req.method() === "POST") {
      expect(req.headers()["x-cryptolab-research"]).toBe("1");
      if (path.endsWith("experiments")) {
        if (options.createError) return r.fulfill({status:options.createError,json:{detail:options.createError === 409 ? "PROTOCOL_CONDITIONS_MISMATCH" : "Ocupado"}});
        created=req.postDataJSON();
        return r.fulfill({json:{id:experimentId,arena_version:"synthetic-test",config:created,protocol_ids:protocolIds}});
      }
      posts++;
      if (options.malformed) return r.fulfill({status:503,contentType:"text/html",body:"Serviço indisponível"});
      if (options.executeError) return r.fulfill({status:options.executeError,json:{detail:"Tempo excedido"}});
      persisted=true;
      return r.fulfill({json:result()});
    }
    if (path.endsWith("/result")) {
      resultChecks++;
      if (options.recoverBusy && resultChecks === 2) return r.fulfill({status:429,json:{detail:"Pesquisa ocupada"}});
      if (persisted || (options.recoverFound && resultChecks > 1)) return r.fulfill({json:result()});
      return r.fulfill({status:409,json:{detail:"ARENA_RESULT_NOT_FOUND"}});
    }
    if (path.endsWith("experiments")) return r.fulfill({json:{experiments:created ? [{id:experimentId,created_at:"2026-11-02T12:00:00Z"}] : []}});
    return r.fulfill({json:{id:experimentId,arena_version:"synthetic-test",config:created,protocol_ids:protocolIds}});
  });
  await page.route("**/api/research/runs/**", r => {
    const id=new URL(r.request().url()).pathname.split("/").pop();
    const pair=phases.flatMap(p => names.map(bot => ({p,bot}))).find(x => runId(x.p,x.bot) === id)!;
    const c=created as {train_start:number;train_end:number;validation_end:number;test_end:number};
    const windows:Record<Phase,[number,number]> = {train:[c.train_start,c.train_end],validation:[c.train_end,c.validation_end],test:[c.validation_end,c.test_end]};
    const [a,b]=windows[pair.p];
    return r.fulfill({json:{id,manifest:{strategy:pair.bot,partition:pair.p,start_time:a,end_time:b},simulation:{equity:[{time:a,equity:"10000",cash:"10000",quantity:"0",drawdown_pct:"0"},{time:b,equity:"10100",cash:"10100",quantity:"0",drawdown_pct:"0"}],trades:[]}}});
  });
  return { getCreated:()=>created, getPosts:()=>posts, getChecks:()=>resultChecks };
}

test("Arena: configura quatro bots, executa ranking com empates e gráficos por janela", async ({page}) => {
  const errors:string[]=[]; page.on("pageerror",e=>errors.push(e.message));
  const mock=await mocks(page);
  await page.goto("/arena");
  await page.getByRole("combobox",{name:"Dataset histórico"}).selectOption(datasetId);
  await page.getByText("Trend Following",{exact:true}).first().click();
  await page.getByLabel("Trend Following · Média rápida").fill("10");
  await page.getByText("RSI Mean Reversion",{exact:true}).first().click();
  await page.getByLabel("RSI Mean Reversion · Período RSI").fill("12");
  await page.getByText("Breakout",{exact:true}).first().click();
  await page.getByLabel("Breakout · Candles anteriores").fill("15");
  await page.getByRole("button",{name:"Criar experimento"}).click();
  await expect(page.getByText("Pronto para pesquisa")).toBeVisible();
  const sent=mock.getCreated() as {strategies:Record<Bot,{parameters:{fast:number;rsi_period:number;lookback:number}}>};
  expect(sent.strategies.trend.parameters.fast).toBe(10);
  expect(sent.strategies.rsi.parameters.rsi_period).toBe(12);
  expect(sent.strategies.breakout.parameters.lookback).toBe(15);
  expect(Object.keys(sent.strategies)).toHaveLength(4);
  await page.getByRole("button",{name:"Executar competição"}).click();
  await expect(page.getByRole("heading",{name:"Resultados da competição"})).toBeVisible();
  await expect(page.getByText("Pesquisa histórica, sem vencedor validado.")).toBeVisible();
  await expect(page.getByText("Amostra insuficiente",{exact:true}).first()).toBeVisible();
  const ranking=page.locator(".arena-ranking tbody tr");
  await expect(ranking).toHaveCount(4);
  await expect(ranking.nth(0)).toContainText("01"); await expect(ranking.nth(1)).toContainText("01");
  await expect(ranking.nth(0)).toContainText("Indefinido");
  await expect(page.getByRole("img",{name:/Curvas de patrimônio/})).toBeVisible();
  await page.getByRole("button",{name:"Trend Following",exact:true}).last().click();
  await expect(page.getByRole("button",{name:"Trend Following",exact:true}).last()).toHaveAttribute("aria-pressed","false");
  await page.getByRole("button",{name:"Treino",exact:true}).click();
  await page.getByRole("button",{name:"Validação",exact:true}).click();
  await page.getByRole("button",{name:"Treino",exact:true}).click();
  await expect(page.getByRole("button",{name:"Treino",exact:true})).toHaveAttribute("aria-pressed","true");
  await expect(page.getByRole("img",{name:/Curvas de patrimônio/})).toBeVisible();
  await ranking.nth(1).getByRole("button").click();
  await expect(page.getByRole("heading",{name:"RSI Mean Reversion"})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test("Arena: histórico restaura resultado sem repetir POST", async ({page}) => {
  const mock=await mocks(page); await page.goto("/arena");
  await page.getByRole("combobox",{name:"Dataset histórico"}).selectOption(datasetId);
  await page.getByLabel("Capital inicial (USDT)").fill("12345");
  await page.getByRole("button",{name:"Criar experimento"}).click();
  await page.getByRole("button",{name:"Executar competição"}).click();
  await expect(page.getByRole("heading",{name:"Resultados da competição"})).toBeVisible();
  await page.getByRole("button",{name:`Consultar experimento ${experimentId}`}).click();
  await expect(page.getByRole("status")).toContainText("Resultado persistido encontrado");
  await expect(page.getByLabel("Capital inicial (USDT)")).toHaveValue("12345");
  expect(mock.getPosts()).toBe(1);
});

test("Arena: timeout consulta resultado e só libera tentativa após confirmação", async ({page}) => {
  const mock=await mocks(page,{executeError:504,recoverBusy:true}); await page.goto("/arena");
  await page.getByRole("combobox",{name:"Dataset histórico"}).selectOption(datasetId);
  await page.getByRole("button",{name:"Criar experimento"}).click();
  await page.getByRole("button",{name:"Executar competição"}).click();
  await expect(page.getByRole("button",{name:"Consultar resultado"})).toBeVisible();
  await expect(page.getByRole("button",{name:"Executar competição"})).toHaveCount(0);
  expect(mock.getPosts()).toBe(1);
  await page.getByRole("button",{name:"Consultar resultado"}).click();
  await expect(page.getByRole("status")).toContainText("Nenhum resultado persistido");
  await expect(page.getByRole("button",{name:"Executar competição"})).toBeEnabled();
  expect(mock.getPosts()).toBe(1);
});

test("Arena: timeout recupera resultado persistido sem novo POST", async ({page}) => {
  const mock=await mocks(page,{executeError:504,recoverFound:true}); await page.goto("/arena");
  await page.getByRole("combobox",{name:"Dataset histórico"}).selectOption(datasetId);
  await page.getByRole("button",{name:"Criar experimento"}).click();
  await page.getByRole("button",{name:"Executar competição"}).click();
  await expect(page.getByRole("heading",{name:"Resultados da competição"})).toBeVisible();
  expect(mock.getPosts()).toBe(1); expect(mock.getChecks()).toBe(2);
});

test("Arena: resposta inválida da execução exige consulta antes de nova tentativa", async ({page}) => {
  const mock=await mocks(page,{malformed:true,recoverBusy:true}); await page.goto("/arena");
  await page.getByRole("combobox",{name:"Dataset histórico"}).selectOption(datasetId);
  await page.getByRole("button",{name:"Criar experimento"}).click();
  await page.getByRole("button",{name:"Executar competição"}).click();
  await expect(page.getByRole("button",{name:"Consultar resultado"})).toBeVisible();
  expect(mock.getPosts()).toBe(1); expect(mock.getChecks()).toBe(2);
});

test("Arena: erro 500 da execução consulta resultado sem repetir POST", async ({page}) => {
  const mock=await mocks(page,{executeError:500,recoverBusy:true}); await page.goto("/arena");
  await page.getByRole("combobox",{name:"Dataset histórico"}).selectOption(datasetId);
  await page.getByRole("button",{name:"Criar experimento"}).click();
  await page.getByRole("button",{name:"Executar competição"}).click();
  await expect(page.getByRole("button",{name:"Consultar resultado"})).toBeVisible();
  expect(mock.getPosts()).toBe(1); expect(mock.getChecks()).toBe(2);
});

for (const status of [409,429]) test(`Arena: erro ${status} não inventa resultados`, async ({page}) => {
  await mocks(page,{createError:status}); await page.goto("/arena");
  await page.getByRole("combobox",{name:"Dataset histórico"}).selectOption(datasetId);
  await page.getByRole("button",{name:"Criar experimento"}).click();
  await expect(page.getByRole("alert").filter({hasText:"Não foi possível concluir"})).toContainText(status === 409 ? "Configuração ou integridade" : "Pesquisa ocupada");
  await expect(page.getByRole("heading",{name:"Resultados da competição"})).toHaveCount(0);
});

test("Arena: catálogo vazio e API indisponível sem fallback", async ({page}) => {
  await mocks(page,{empty:true}); await page.goto("/arena");
  await expect(page.getByText("Nenhum dataset aprovado.",{exact:false})).toBeVisible();
  await expect(page.getByRole("button",{name:"Criar experimento"})).toBeDisabled();
  await expect(page.getByText("Nenhuma competição selecionada",{exact:true})).toBeVisible();
});

test("Arena: backend indisponível apresenta erro sem inventar dados", async ({page}) => {
  await page.route("**/api/**", r => r.fulfill({status:503,json:{detail:"Backend indisponível"}}));
  await page.goto("/arena");
  await expect(page.getByRole("alert").filter({hasText:"Não foi possível concluir"})).toContainText("Backend indisponível");
  await expect(page.getByRole("heading",{name:"Resultados da competição"})).toHaveCount(0);
});

test("Arena real: catálogo → competição → ranking e curvas persistidas", async ({page,request},info) => {
  test.skip(process.env.CRYPTOLAB_ARENA_SMOKE !== "1","Requer API e dataset aprovado local");
  test.setTimeout(120000);
  const real="f3b2e55b1cc373d448efa3676c63064cb482c86be4ebd7442bce573134f972c6";
  await page.goto("/arena");
  await page.getByRole("combobox",{name:"Dataset histórico"}).selectOption(real);
  await page.getByRole("button",{name:"Criar experimento"}).click();
  await expect(page.getByRole("heading",{name:"Pronto para pesquisa"})).toBeVisible({timeout:30000});
  const execute=page.getByRole("button",{name:"Executar competição"});
  if (await execute.isVisible()) await execute.click();
  await expect(page.getByRole("heading",{name:"Resultados da competição"})).toBeVisible({timeout:90000});
  await expect(page.getByRole("img",{name:/Curvas de patrimônio/})).toBeVisible({timeout:30000});
  await expect(page.getByRole("button",{name:"Reexecutar competição"})).toBeEnabled();
  await expect(page.getByText("Pesquisa histórica, sem vencedor validado.")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:`artifacts/arena-${info.project.name}.png`,fullPage:true});
  expect((await request.post("/api/arena/orders",{data:{}})).status()).toBe(404);
  expect((await request.post("/api/arena/execute",{data:{},headers:{origin:"https://evil.invalid","X-CryptoLab-Research":"1"}})).status()).toBe(403);
});
