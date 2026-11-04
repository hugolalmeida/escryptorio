"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Check, Database, FlaskConical, LockKeyhole, Play, RefreshCw, ShieldCheck, Swords } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ArenaChart } from "@/components/arena-chart";
import { historyFetch, timeframe, utcTime, type DatasetManifest } from "@/lib/history";
import { number, partitions, researchFetch, strategies, type Partition, type Result, type StrategyId } from "@/lib/research";
import type { Interval } from "@/lib/market";
import { ArenaRequestError, arenaFetch, colors, ids, type ArenaConfig, type ArenaResult, type Experiment,
  type ExperimentSummary, type Parameters, type Runs } from "@/lib/arena";

type ParamsForm = { fast:string; slow:string; trend_entry:string; trend_exit:string; max_atr_ratio:string; rsi_period:string;
  rsi_entry:string; rsi_exit:string; trend_filter:boolean; lookback:string; volume_multiple:string; stop_fraction:string; target_fraction:string };
const defaultParams = (): ParamsForm => ({fast:"20",slow:"50",trend_entry:"cross",trend_exit:"averages",max_atr_ratio:"",
  rsi_period:"14",rsi_entry:"30",rsi_exit:"60",trend_filter:false,lookback:"20",volume_multiple:"",stop_fraction:"0.03",target_fraction:"0.06"});
const makeParams = () => Object.fromEntries(ids.map(id => [id,defaultParams()])) as Record<StrategyId,ParamsForm>;
const labels: Partial<Record<keyof ParamsForm,string>> = {fast:"Média rápida",slow:"Média lenta",max_atr_ratio:"ATR / preço máximo (opcional)",
  rsi_period:"Período RSI",rsi_entry:"RSI de recuperação",rsi_exit:"RSI de saída",lookback:"Candles anteriores",volume_multiple:"Multiplicador de volume (opcional)",
  stop_fraction:"Stop (fração)",target_fraction:"Alvo (fração)"};
const paramFields: Record<StrategyId,(keyof ParamsForm)[]> = {trend:["fast","slow","max_atr_ratio","stop_fraction","target_fraction"],
  rsi:["rsi_period","rsi_entry","rsi_exit","slow","stop_fraction","target_fraction"], breakout:["lookback","volume_multiple","stop_fraction","target_fraction"], buy_hold:[]};
const dateInput = (t:number) => new Date(t*1000).toISOString().slice(0,16);
const seconds = (v:string) => Date.parse(`${v}:00Z`)/1000;
function parameters(p:ParamsForm):Parameters {
  return {...p, fast:Number(p.fast), slow:Number(p.slow), rsi_period:Number(p.rsi_period), lookback:Number(p.lookback),
    max_atr_ratio:p.max_atr_ratio || null,volume_multiple:p.volume_multiple || null};
}
function displayError(error:unknown) {
  if (error instanceof ArenaRequestError && error.status === 429) return "Pesquisa ocupada. Aguarde a execução em andamento e consulte novamente.";
  if (error instanceof ArenaRequestError && error.status === 409) return `Configuração ou integridade recusada: ${error.message}`;
  return error instanceof Error ? error.message : "Não foi possível consultar a Arena.";
}
// Serialize curve reads across rapid period changes as well as within each period.
let curveQueue: Promise<void> = Promise.resolve();
async function queuedRun(id:string, cancelled:() => boolean):Promise<Result | undefined> {
  const previous = curveQueue;
  let release = () => {};
  curveQueue = new Promise<void>(resolve => { release = resolve; });
  await previous;
  try { return cancelled() ? undefined : await researchFetch<Result>(`runs/${id}`); }
  finally { release(); }
}

export function Arena() {
  const [datasets,setDatasets] = useState<DatasetManifest[]>([]);
  const [history,setHistory] = useState<ExperimentSummary[]>([]);
  const [selected,setSelected] = useState("");
  const [dates,setDates] = useState({train_start:"",train_end:"",validation_end:"",test_end:""});
  const [capital,setCapital] = useState("10000"), [fee,setFee] = useState("0.001"), [slippage,setSlippage] = useState("0.0005");
  const [risk,setRisk] = useState("0.01"), [exposure,setExposure] = useState("1"), [policy,setPolicy] = useState("liquidate");
  const [params,setParams] = useState(makeParams);
  const [experiment,setExperiment] = useState<Experiment>();
  const [result,setResult] = useState<ArenaResult>();
  const [partition,setPartition] = useState<Partition>("test");
  const [bot,setBot] = useState<StrategyId>("trend");
  const [runs,setRuns] = useState<Runs>({});
  const [runsLoading,setRunsLoading] = useState(false), [runsError,setRunsError] = useState("");
  const [runsRefresh,setRunsRefresh] = useState(0);
  const [loading,setLoading] = useState(true), [pending,setPending] = useState(false);
  const [error,setError] = useState(""), [notice,setNotice] = useState("");
  const [recovery,setRecovery] = useState<"clear"|"checking"|"uncertain">("clear");
  const [tradePage,setTradePage] = useState(0), [equityPage,setEquityPage] = useState(0);
  const dataset = datasets.find(d => d.dataset_id === selected);

  async function loadCatalog() {
    setLoading(true); setError("");
    try {
      const [catalog,previous] = await Promise.all([historyFetch<{datasets:DatasetManifest[]}>("datasets"),arenaFetch<{experiments:ExperimentSummary[]}>("experiments")]);
      setDatasets(catalog.datasets); setHistory(previous.experiments);
    } catch (e) { setError(displayError(e)); } finally { setLoading(false); }
  }
  useEffect(() => { void loadCatalog(); }, []);

  useEffect(() => {
    let cancelled = false;
    setRuns({}); setRunsError("");
    if (!result) return;
    setRunsLoading(true);
    const current = result;
    async function load() {
      const next: Runs = {};
      try {
        // The local research API shares a one-request gate; never issue four GETs concurrently.
        for (const id of ids) {
          const run = await queuedRun(current.run_ids[partition][id], () => cancelled);
          if (cancelled) return;
          if (!run || run.id !== current.run_ids[partition][id] || run.manifest.partition !== partition || run.manifest.strategy !== id ||
              run.manifest.start_time !== current.rankings[partition].start_time || run.manifest.end_time !== current.rankings[partition].end_time)
            throw new Error("Execução incompatível com a janela da Arena.");
          next[id] = run;
        }
        const reference = next[ids[0]]?.simulation.equity;
        if (!reference?.length || ids.some(id => {
          const points = next[id]?.simulation.equity;
          return !points || points.length !== reference.length || points.some((point,index) => point.time !== reference[index].time);
        })) throw new Error("As curvas não compartilham os mesmos timestamps; comparação indisponível.");
        if (!cancelled) setRuns(next);
      } catch (e) { if (!cancelled) setRunsError(e instanceof Error ? e.message : "Falha ao carregar curvas."); }
      finally { if (!cancelled) setRunsLoading(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [result,partition,runsRefresh]);

  function chooseDataset(id:string) {
    setSelected(id);
    const d = datasets.find(x => x.dataset_id === id);
    if (!d) { setDates({train_start:"",train_end:"",validation_end:"",test_end:""}); return; }
    const step = d.interval === "D" ? 86400 : Number(d.interval)*60;
    const reserve = Math.min(500,Math.floor(d.candle_count/4)), n = d.candle_count-reserve;
    setDates({train_start:dateInput(d.start_time+reserve*step),train_end:dateInput(d.start_time+(reserve+Math.floor(n*.6))*step),
      validation_end:dateInput(d.start_time+(reserve+Math.floor(n*.8))*step),test_end:dateInput(d.end_time)});
  }
  async function checkResult(id:string, uncertain:boolean) {
    setRecovery("checking");
    try {
      const saved = await arenaFetch<ArenaResult>(`experiments/${id}/result`);
      setResult(saved); setPartition("test"); setRecovery("clear"); setError("");
      setNotice("Resultado persistido encontrado e verificado.");
    } catch (e) {
      if (e instanceof ArenaRequestError && e.status === 409 && e.message === "ARENA_RESULT_NOT_FOUND") {
        setResult(undefined); setRecovery("clear"); setError("");
        setNotice("Nenhum resultado persistido. Você pode executar a competição manualmente.");
      } else {
        setRecovery(uncertain ? "uncertain" : "clear");
        setError(displayError(e));
      }
    }
  }
  async function create() {
    if (!dataset) return;
    setPending(true); setError(""); setNotice("");
    try {
      const config = {dataset_hash:dataset.dataset_id,symbol:dataset.symbol,interval:dataset.interval,
        ...Object.fromEntries(Object.entries(dates).map(([key,value]) => [key,seconds(value)])),
        backtest:{capital,risk_fraction:risk,exposure_fraction:exposure,final_policy:policy,costs:{fee_rate:fee,slippage_rate:slippage}},
        strategies:Object.fromEntries(ids.map(id => [id,{version:"1",parameters:parameters(params[id])}]))};
      const created = await arenaFetch<Experiment>("experiments",config);
      setExperiment(created); setResult(undefined); setRecovery("clear");
      setHistory((await arenaFetch<{experiments:ExperimentSummary[]}>("experiments")).experiments);
      await checkResult(created.id,false);
    } catch (e) { setError(displayError(e)); } finally { setPending(false); }
  }
  async function execute() {
    if (!experiment || recovery !== "clear") return;
    setPending(true); setError(""); setNotice("");
    try {
      const completed = await arenaFetch<ArenaResult>("execute",{experiment_id:experiment.id});
      setResult(completed); setPartition("test"); setNotice("Competição concluída e persistida. Teste fora da amostra selecionado.");
    } catch (e) {
      if (e instanceof ArenaRequestError && (e.status === 0 || e.status >= 500)) {
        setError("A execução pode ainda estar em andamento. Consultando o resultado antes de permitir nova tentativa.");
        await checkResult(experiment.id,true);
      } else setError(displayError(e));
    } finally { setPending(false); }
  }
  async function openExperiment(id:string) {
    setPending(true); setError(""); setNotice(""); setResult(undefined); setRuns({}); setExperiment(undefined);
    try {
      const saved = await arenaFetch<Experiment>(`experiments/${id}`);
      const c = saved.config;
      setExperiment(saved); setSelected(c.dataset_hash); setRecovery("clear");
      setDates({train_start:dateInput(c.train_start),train_end:dateInput(c.train_end),validation_end:dateInput(c.validation_end),test_end:dateInput(c.test_end)});
      setCapital(c.backtest.capital); setRisk(c.backtest.risk_fraction); setExposure(c.backtest.exposure_fraction);
      setFee(c.backtest.costs.fee_rate); setSlippage(c.backtest.costs.slippage_rate); setPolicy(c.backtest.final_policy);
      setParams(Object.fromEntries(ids.map(key => {
        const p = c.strategies[key].parameters;
        return [key,{...p,fast:String(p.fast),slow:String(p.slow),rsi_period:String(p.rsi_period),lookback:String(p.lookback),
          max_atr_ratio:p.max_atr_ratio ?? "",volume_multiple:p.volume_multiple ?? ""}];
      })) as Record<StrategyId,ParamsForm>);
      await checkResult(id,false);
    } catch (e) { setError(displayError(e)); } finally { setPending(false); }
  }
  async function manualCheck() {
    if (!experiment) return;
    setPending(true); setError(""); setNotice("");
    try { await checkResult(experiment.id,true); } finally { setPending(false); }
  }
  function reset() { setExperiment(undefined); setResult(undefined); setRecovery("clear"); setError(""); setNotice(""); }
  const ranking = result?.rankings[partition];
  const selectedEntry = ranking?.entries.find(e => e.strategy === bot);
  const currentRun = runs[bot];

  return <main id="main-content" className="page arena-page">
    <div className="page-heading arena-heading"><div><div className="arena-kicker"><Swords size={14}/> LABORATÓRIO DE ESTRATÉGIAS <span> / </span> PESQUISA HISTÓRICA</div><h1>Arena de Bots</h1><p>Compare estratégias sob as mesmas condições. Dados históricos, decisões reproduzíveis.</p></div><span className="tag"><ShieldCheck size={14}/> Simulação Spot</span></div>
    <div className="arena-intro"><div><span className="arena-intro-icon"><FlaskConical size={20}/></span><div><strong>Uma competição. Quatro hipóteses.</strong><p>Cada bot recebe capital virtual independente, o mesmo mercado e as mesmas premissas de custos.</p></div></div><Link href="/history" className="text-link">Gerenciar dados <ArrowRight size={14}/></Link></div>
    {error && <div className="data-alert arena-alert" role="alert"><div><strong>Não foi possível concluir</strong><p>{error}</p></div><Button variant="ghost" disabled={pending} onClick={loadCatalog}>Atualizar dados</Button></div>}
    {notice && <p className="history-notice" role="status"><Check size={15}/>{notice}</p>}
    <div className="arena-layout"><div className="arena-primary">
      <section className="panel arena-config"><div className="panel-heading"><div><div className="arena-section-label">01 / CONFIGURAÇÃO</div><h2>Preparar competição</h2><p>Selecione um dataset aprovado e congele as condições antes de executar.</p></div>{experiment && <span className="tag"><LockKeyhole size={12}/> Congelada</span>}</div>
        <form onSubmit={e => {e.preventDefault();void create();}}><fieldset disabled={pending || !!experiment}><legend className="sr-only">Configuração da competição</legend>
          <div className="arena-fields arena-dataset-fields"><label>Dataset histórico<select required value={selected} onChange={e => chooseDataset(e.target.value)}><option value="">{loading ? "Carregando datasets…" : "Selecione um dataset aprovado"}</option>{selected && !dataset && experiment && <option value={selected}>{experiment.config.symbol} · {timeframe(experiment.config.interval as Interval)} · {selected.slice(0,10)} (fora do catálogo recente)</option>}{datasets.map(d => <option key={d.dataset_id} value={d.dataset_id}>{d.symbol} · {timeframe(d.interval)} · {d.candle_count} candles · {d.dataset_id.slice(0,10)}</option>)}</select></label>
            <div className="arena-derived"><span>ATIVO / TIMEFRAME</span><strong>{dataset ? `${dataset.symbol} · ${timeframe(dataset.interval)}` : experiment ? `${experiment.config.symbol} · ${timeframe(experiment.config.interval as Interval)}` : "—"}</strong><small>Definidos pelo dataset</small></div></div>
          {!loading && !datasets.length && <p className="arena-hint">Nenhum dataset aprovado. <Link href="/history" className="text-link">Solicitar dados históricos</Link></p>}
          {dataset && <p className="arena-hint">Disponível: {utcTime(dataset.start_time)} → {utcTime(dataset.end_time)} UTC · limite final exclusivo.</p>}
          <div className="arena-subheading"><span>JANELAS CRONOLÓGICAS</span><span>UTC · FIM EXCLUSIVO</span></div>
          <div className="arena-fields arena-four">{Object.entries({train_start:"Início do treino",train_end:"Início da validação",validation_end:"Início do teste",test_end:"Fim do teste"}).map(([key,label]) => <label key={key}>{label}<input type="datetime-local" required value={dates[key as keyof typeof dates]} onChange={e => setDates({...dates,[key]:e.target.value})}/></label>)}</div>
          <p className="arena-hint">Histórico anterior aquece os indicadores. Cada janela reinicia o capital; parâmetros ficam congelados antes do teste.</p>
          <div className="arena-subheading"><span>PREMISSAS COMPARTILHADAS</span><span>MESMO CAPITAL E CUSTOS</span></div>
          <div className="arena-fields arena-three">
            <label>Capital inicial (USDT)<input required inputMode="decimal" value={capital} onChange={e => setCapital(e.target.value)}/></label>
            <label>Taxa por fill (fração)<input required inputMode="decimal" value={fee} onChange={e => setFee(e.target.value)}/></label>
            <label>Slippage (fração)<input required inputMode="decimal" value={slippage} onChange={e => setSlippage(e.target.value)}/></label>
            <label>Risco planejado (fração)<input required inputMode="decimal" value={risk} onChange={e => setRisk(e.target.value)}/></label>
            <label>Exposição máxima (fração)<input required inputMode="decimal" value={exposure} onChange={e => setExposure(e.target.value)}/></label>
            <label>Encerramento<select value={policy} onChange={e => setPolicy(e.target.value)}><option value="liquidate">Liquidar no fim com custos</option><option value="mark_to_market">Marcar posição a mercado</option></select></label>
          </div><p className="arena-hint">Use ponto decimal: 0.01 = 1%. Custos e slippage são hipóteses, não taxas da conta.</p>
          <div className="arena-subheading"><span>PARÂMETROS POR ESTRATÉGIA</span><span>VERSÃO 1 · EXPERIMENTAL</span></div>
          <div className="arena-strategies">{ids.map(id => <details key={id} className="arena-strategy"><summary><span><i style={{background:colors[id]}}/>{strategies[id]}</span><small>{id === "buy_hold" ? "BENCHMARK" : "LONG ONLY"}</small></summary>
            {id === "buy_hold" ? <p>Compra única, sem stop ou alvo. Risco por stop não se aplica ao benchmark.</p> : <div className="arena-fields arena-three">
              {paramFields[id].map(key => <label key={key}>{labels[key]}<input aria-label={`${strategies[id]} · ${labels[key]}`} inputMode="decimal" value={String(params[id][key])} onChange={e => setParams({...params,[id]:{...params[id],[key]:e.target.value}})}/></label>)}
              {id === "trend" && <><label>Entrada<select aria-label="Trend Following · Entrada" value={params.trend.trend_entry} onChange={e => setParams({...params,trend:{...params.trend,trend_entry:e.target.value}})}><option value="cross">Cruzamento ascendente</option><option value="state">Estado acima da lenta</option></select></label><label>Saída<select aria-label="Trend Following · Saída" value={params.trend.trend_exit} onChange={e => setParams({...params,trend:{...params.trend,trend_exit:e.target.value}})}><option value="averages">Rápida ≤ lenta</option><option value="close_fast">Fechamento abaixo da rápida</option></select></label></>}
              {id === "rsi" && <label>Filtro de tendência<select aria-label="RSI Mean Reversion · Filtro de tendência" value={String(params.rsi.trend_filter)} onChange={e => setParams({...params,rsi:{...params.rsi,trend_filter:e.target.value === "true"}})}><option value="false">Sem filtro</option><option value="true">Acima da SMA lenta</option></select></label>}
            </div>}</details>)}</div>
        </fieldset><div className="arena-form-actions"><div><LockKeyhole size={14}/><span>Quatro carteiras virtuais independentes.<br/>Nenhuma conta privada conectada.</span></div>{experiment ? <Button type="button" variant="outline" disabled={pending || recovery !== "clear"} onClick={reset}>Nova configuração</Button> : <Button type="submit" disabled={pending || loading || !dataset}><LockKeyhole size={14}/> Criar experimento</Button>}</div></form>
      </section>
      {experiment && <section className="panel arena-execution"><div className="panel-heading"><div><div className="arena-section-label">02 / EXPERIMENTO CONGELADO</div><h2>Pronto para pesquisa</h2><p>{experiment.config.symbol} · {timeframe(experiment.config.interval as Interval)} · capital {number(experiment.config.backtest.capital)} USDT por bot</p></div><span className="arena-badge">PROCEDIMENTO LOCAL</span></div>
        <div className="arena-execution-body"><div className="arena-hash"><span>EXPERIMENTO SHA-256</span><code>{experiment.id}</code></div><div className="arena-run-actions"><div><strong>{pending ? "Processando pesquisa…" : recovery === "uncertain" ? "Resultado ainda não confirmado" : result ? "Resultado disponível" : "Aguardando execução"}</strong><p>{pending ? "O backend processa as janelas em sequência. Não há progresso percentual disponível." : recovery === "uncertain" ? "Consulte o resultado antes de tentar novamente." : "Treino → validação → teste fora da amostra."}</p></div>
          {recovery === "uncertain" ? <Button type="button" disabled={pending} onClick={manualCheck}><RefreshCw size={14}/> Consultar resultado</Button> : <Button type="button" disabled={pending || recovery !== "clear"} onClick={execute}><Play size={14}/>{result ? "Reexecutar competição" : "Executar competição"}</Button>}</div>
          <details className="arena-details"><summary>Ver configurações congeladas</summary><pre>{JSON.stringify({config:experiment.config,protocol_ids:experiment.protocol_ids},null,2)}</pre></details></div></section>}
      {result && ranking && <>
        <section className="panel arena-results"><div className="panel-heading"><div><div className="arena-section-label">03 / COMPARAÇÃO</div><h2>Resultados da competição</h2><p>Ranking líquido conforme calculado pelo motor, com custos em cada fill.</p></div><span className="arena-badge">{ranking.out_of_sample ? "FORA DA AMOSTRA" : "PESQUISA HISTÓRICA"}</span></div>
          <div className="arena-tabs" role="group" aria-label="Período de avaliação">{(["train","validation","test"] as Partition[]).map(p => <button key={p} type="button" aria-pressed={partition === p} onClick={() => {setPartition(p);setTradePage(0);setEquityPage(0);}}>{partitions[p]}{p === "test" && <span>OOS</span>}</button>)}</div>
          <div className="arena-window"><div><strong>{ranking.out_of_sample ? "Teste fora da amostra" : partitions[partition]}</strong><span>{utcTime(ranking.start_time)} → {utcTime(ranking.end_time)} UTC</span></div><span>{ranking.insufficient_sample ? "Amostra insuficiente" : "Amostra em avaliação"}</span></div>
          <div className="arena-risk-note"><strong>Pesquisa histórica, sem vencedor validado.</strong> {ranking.insufficient_sample && "Amostra insuficiente para ao menos um participante. "}Retornos passados não preveem resultados futuros.</div>
          <p className="arena-scroll-hint">Deslize a tabela para consultar todas as métricas.</p><div className="table-scroll"><table className="arena-ranking"><thead><tr><th>Posição / estratégia</th><th>Retorno líquido</th><th>Drawdown máx.</th><th>Profit factor</th><th>Acerto</th><th>Trades</th><th>Custos USDT</th><th>Exposição</th><th>vs. Buy & Hold</th></tr></thead><tbody>{ranking.entries.map(entry => <tr key={entry.strategy} className={bot === entry.strategy ? "arena-row-selected" : ""}><td><button type="button" className="arena-bot-choice" onClick={() => {setBot(entry.strategy);setTradePage(0);setEquityPage(0);}}><span className="arena-rank">{String(entry.rank).padStart(2,"0")}</span><i style={{background:colors[entry.strategy]}}/><span>{strategies[entry.strategy]}<small>{entry.insufficient_sample ? "Amostra insuficiente" : "Em pesquisa"}</small></span></button></td><td className={Number(entry.net_return_pct) < 0 ? "arena-negative" : "arena-positive"}>{number(entry.net_return_pct)}%</td><td>{number(entry.max_drawdown_pct)}%</td><td title={entry.profit_factor === null ? entry.undefined.profit_factor : undefined}>{number(entry.profit_factor)}</td><td title={entry.win_rate_pct === null ? entry.undefined.win_rate_pct : undefined}>{entry.win_rate_pct === null ? "Indefinido" : `${number(entry.win_rate_pct)}%`}</td><td>{entry.closed_trades}</td><td>{number(entry.total_costs)}</td><td>{number(entry.exposure_pct)}%</td><td>{number(entry.excess_return_pp)} pp</td></tr>)}</tbody></table></div>
          {ranking.entries.some(e => e.profit_factor === null || e.win_rate_pct === null) && <p className="arena-hint arena-pad">Métricas indefinidas: {ranking.entries.flatMap(e => Object.entries(e.undefined).filter(([key]) => ["profit_factor","win_rate_pct"].includes(key)).map(([key,reason]) => `${strategies[e.strategy]} · ${key}: ${reason}`)).join("; ")}.</p>}
        </section>
        <section className="panel arena-chart-panel"><div className="panel-heading"><div><div className="arena-section-label">04 / PATRIMÔNIO</div><h2>Evolução comparativa</h2><p>Quatro carteiras · mesmo período · valores em USDT</p></div><span className="tag">{partitions[partition]} · UTC</span></div>
          {runsLoading ? <div className="arena-empty"><RefreshCw size={21} className="spin"/><strong>Carregando execuções verificadas…</strong></div> : runsError ? <div className="arena-empty"><strong>Curvas indisponíveis</strong><p>{runsError}</p><Button variant="outline" onClick={() => setRunsRefresh(n => n+1)}>Tentar novamente</Button></div> : ids.every(id => runs[id]?.simulation.equity.length) ? <ArenaChart runs={runs}/> : <div className="arena-empty"><strong>Sem dados de patrimônio</strong><p>Nenhum ponto foi fornecido pelas execuções persistidas.</p></div>}</section>
        <section className="panel arena-detail"><div className="panel-heading"><div><div className="arena-section-label">05 / DETALHE DO BOT</div><h2>{strategies[bot]}</h2><p>Selecione uma estratégia no ranking para inspecionar suas operações.</p></div><span className="tag">{partitions[partition]}</span></div>
          {selectedEntry && <><div className="arena-detail-metrics">{[["Retorno líquido",`${number(selectedEntry.net_return_pct)}%`],["Drawdown máximo",`${number(selectedEntry.max_drawdown_pct)}%`],["Custos totais",`${number(selectedEntry.total_costs)} USDT`],["Operações",String(selectedEntry.closed_trades)],["Expectativa por trade",selectedEntry.expectancy === null ? "Indefinido" : `${number(selectedEntry.expectancy)} USDT`]].map(([label,value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
            {selectedEntry.expectancy === null && <p className="arena-hint arena-pad">Expectativa indefinida: {selectedEntry.undefined.expectancy ?? "sem trades encerrados"}.</p>}
            <div className="arena-detail-hashes"><div><span>EXECUÇÃO</span><code>{selectedEntry.run_id}</code></div><div><span>PROTOCOLO</span><code>{selectedEntry.protocol_id}</code></div></div>
            <details className="arena-details arena-pad"><summary>Parâmetros congelados · versão {selectedEntry.strategy_version}</summary><pre>{JSON.stringify(selectedEntry.parameters,null,2)}</pre></details>
            {currentRun && <details className="arena-details arena-pad"><summary>Patrimônio do bot · valores exatos</summary><div className="table-scroll"><table><thead><tr><th>UTC</th><th>Patrimônio USDT</th><th>Saldo USDT</th><th>Drawdown %</th></tr></thead><tbody>{currentRun.simulation.equity.slice(equityPage*25,(equityPage+1)*25).map(p => <tr key={p.time}><td>{utcTime(p.time)}</td><td>{p.equity}</td><td>{p.cash}</td><td>{p.drawdown_pct}</td></tr>)}</tbody></table></div><div className="backtest-pagination"><Button variant="ghost" disabled={!equityPage} onClick={() => setEquityPage(equityPage-1)}>Anterior</Button><span>{equityPage+1} / {Math.ceil(currentRun.simulation.equity.length/25)}</span><Button variant="ghost" disabled={(equityPage+1)*25 >= currentRun.simulation.equity.length} onClick={() => setEquityPage(equityPage+1)}>Próxima</Button></div></details>}
            <div className="arena-trades-title">Operações encerradas <span>{selectedEntry.closed_trades}</span></div>
            {runsLoading ? <p className="arena-hint arena-pad">Carregando operações…</p> : runsError ? <p className="arena-hint arena-pad">Operações indisponíveis; tente carregar as curvas novamente.</p> : !currentRun?.simulation.trades.length ? <p className="arena-hint arena-pad">Nenhum trade encerrado nesta janela.</p> : <><div className="table-scroll"><table><thead><tr><th>Entrada / saída UTC</th><th>Quantidade</th><th>Preços efetivos</th><th>PnL líquido USDT</th><th>Motivo de saída</th></tr></thead><tbody>{currentRun.simulation.trades.slice(tradePage*10,(tradePage+1)*10).map((trade,i) => <tr key={i}><td>{utcTime(trade.entry.time)}<span className="history-cell-sub">{utcTime(trade.exit.time)}</span></td><td>{trade.entry.quantity}</td><td>{number(trade.entry.price,4)} / {number(trade.exit.price,4)}</td><td>{number(trade.pnl,4)}</td><td>{trade.exit.reason}</td></tr>)}</tbody></table></div><div className="backtest-pagination"><Button variant="ghost" disabled={!tradePage} onClick={() => setTradePage(tradePage-1)}>Anterior</Button><span>{tradePage+1} / {Math.ceil(currentRun.simulation.trades.length/10)}</span><Button variant="ghost" disabled={(tradePage+1)*10 >= currentRun.simulation.trades.length} onClick={() => setTradePage(tradePage+1)}>Próxima</Button></div></>}
          </>}</section>
        <section className="panel arena-provenance"><div className="panel-heading"><div><div className="arena-section-label">06 / PROVENIÊNCIA</div><h2>Pesquisa reproduzível</h2></div><ShieldCheck size={18}/></div><div className="arena-detail-hashes"><div><span>RESULTADO DA ARENA</span><code>{result.id}</code></div><div><span>DATASET HISTÓRICO</span><code>{experiment?.config.dataset_hash}</code></div></div><p className="arena-hint arena-pad">Fills, custos e patrimônio completos podem ser consultados em Backtesting pelo hash da execução.</p></section>
      </>}
      {!result && <section className="panel arena-empty"><Swords size={25}/><strong>Nenhuma competição selecionada</strong><p>Crie um experimento ou consulte o histórico. Resultados aparecerão somente após uma execução persistida.</p></section>}
    </div><aside className="arena-aside"><section className="panel arena-aside-panel"><div className="panel-heading"><h2>Protocolo da Arena</h2><Database size={16}/></div><div className="arena-aside-body"><div className="arena-step"><span>01</span><div><strong>Dados aprovados</strong><p>Dataset verificado por SHA-256.</p></div></div><div className="arena-step"><span>02</span><div><strong>Condições equivalentes</strong><p>Capital, custos e janelas compartilhados.</p></div></div><div className="arena-step"><span>03</span><div><strong>Teste fora da amostra</strong><p>Parâmetros congelados antes da execução.</p></div></div></div></section>
      <section className="panel arena-aside-panel"><div className="panel-heading"><h2>Premissas e limites</h2><ShieldCheck size={16}/></div><div className="arena-aside-body arena-limits"><p>Simulação histórica, sem garantia de desempenho futuro.</p><p>Custos e slippage são hipóteses. Gaps podem exceder o risco planejado.</p><p>Buy & Hold usa exposição diferente das estratégias com stop.</p><p>Mack reservada como não validada; não participa da competição.</p></div></section>
      <section className="panel arena-aside-panel"><div className="panel-heading"><h2>Experimentos anteriores</h2><Button variant="ghost" size="icon" aria-label="Atualizar histórico" disabled={pending || loading} onClick={loadCatalog}><RefreshCw size={15}/></Button></div><div className="arena-history">{loading ? <p>Consultando histórico…</p> : !history.length ? <p>Nenhuma competição persistida.</p> : history.map(item => <button key={item.id} type="button" disabled={pending} onClick={() => openExperiment(item.id)} aria-label={`Consultar experimento ${item.id}`}><span><code>{item.id.slice(0,14)}…</code><small>{item.created_at.replace("T"," ").slice(0,16)} UTC</small></span><ArrowRight size={14}/></button>)}</div></section></aside></div>
  </main>;
}
