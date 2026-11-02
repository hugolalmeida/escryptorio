"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FlaskConical, LockKeyhole, Play, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EquityChart } from "@/components/equity-chart";
import { historyFetch, timeframe, utcTime, type DatasetManifest } from "@/lib/history";
import { number, partitions, researchFetch, strategies, type FrozenProtocol, type Partition, type Result, type RunSummary, type StrategyId } from "@/lib/research";

const defaults = { fast: "20", slow: "50", rsi_period: "14", rsi_entry: "30", rsi_exit: "60", lookback: "20",
  stop_fraction: "0.03", target_fraction: "0.06", max_atr_ratio: "", volume_multiple: "" };
const labels: Record<keyof typeof defaults, string> = { fast: "Média rápida", slow: "Média lenta / filtro", rsi_period: "Período RSI",
  rsi_entry: "RSI de recuperação", rsi_exit: "RSI de saída", lookback: "Candles de resistência", stop_fraction: "Stop (fração)",
  target_fraction: "Alvo (fração)", max_atr_ratio: "ATR / preço máximo (opcional)", volume_multiple: "Multiplicador de volume (opcional)" };
const dateInput = (t: number) => new Date(t*1000).toISOString().slice(0,16);
const seconds = (v: string) => Date.parse(`${v}:00Z`)/1000;

export function Backtesting() {
  const [datasets, setDatasets] = useState<DatasetManifest[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [interval, setInterval] = useState("60");
  const [strategy, setStrategy] = useState<StrategyId>("trend");
  const [parameters, setParameters] = useState(defaults);
  const [entry, setEntry] = useState("cross");
  const [exit, setExit] = useState("averages");
  const [filter, setFilter] = useState(false);
  const [capital, setCapital] = useState("10000");
  const [fee, setFee] = useState("0.001");
  const [slippage, setSlippage] = useState("0.0005");
  const [risk, setRisk] = useState("0.01");
  const [exposure, setExposure] = useState("1");
  const [policy, setPolicy] = useState("liquidate");
  const [dates, setDates] = useState({ train_start: "", train_end: "", validation_end: "", test_end: "" });
  const [partition, setPartition] = useState<Partition>("train");
  const [protocol, setProtocol] = useState("");
  const [result, setResult] = useState<Result>();
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tradePage, setTradePage] = useState(0);
  const [equityPage, setEquityPage] = useState(0);

  async function load() {
    setLoading(true); setError("");
    try {
      const [catalog, previous] = await Promise.all([historyFetch<{datasets: DatasetManifest[]}>("datasets"), researchFetch<{runs: RunSummary[]}>("runs")]);
      setDatasets(catalog.datasets); setRuns(previous.runs);
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  function choose(id: string) {
    setSelected(id);
    const dataset = datasets.find(d => d.dataset_id === id);
    if (!dataset) return;
    const step = dataset.interval === "D" ? 86400 : Number(dataset.interval)*60;
    // Reserve 500 candles when possible, enough for the largest configured indicator.
    // Small datasets retain room for three windows and show explicit warm-up errors if unsuitable.
    const reserve = Math.min(500, Math.floor(dataset.candle_count/4));
    const count = dataset.candle_count-reserve;
    setDates({ train_start: dateInput(dataset.start_time+reserve*step),
      train_end: dateInput(dataset.start_time+(reserve+Math.floor(count*.6))*step),
      validation_end: dateInput(dataset.start_time+(reserve+Math.floor(count*.8))*step), test_end: dateInput(dataset.end_time) });
  }
  async function action(fn: () => Promise<void>) {
    setPending(true); setError(""); setNotice("");
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setPending(false); }
  }
  async function freeze() {
    await action(async () => {
      const parsed = Object.fromEntries(Object.entries(parameters).map(([k,v]) => [k,
        ["fast","slow","rsi_period","lookback"].includes(k) ? Number(v) : v === "" ? null : v]));
      const p = await researchFetch<{id: string}>("protocols", { dataset_hash: selected, strategy,
        parameters: { ...parsed, trend_entry: entry, trend_exit: exit, trend_filter: filter },
        config: { capital, risk_fraction: risk, exposure_fraction: exposure, final_policy: policy, costs: { fee_rate: fee, slippage_rate: slippage } },
        ...Object.fromEntries(Object.entries(dates).map(([k,v]) => [k,seconds(v)])) });
      setProtocol(p.id); setPartition("train"); setNotice("Protocolo congelado. Execute treino e validação antes do teste fora da amostra.");
    });
  }
  async function execute() {
    await action(async () => {
      setResult(await researchFetch<Result>("runs", { protocol_id: protocol, partition }));
      setTradePage(0); setEquityPage(0);
      setRuns((await researchFetch<{runs: RunSummary[]}>("runs")).runs);
      setNotice("Backtest concluído e persistido. Resultado identificado por SHA-256.");
    });
  }
  async function resume(run: RunSummary) {
    await action(async () => {
      // Research API serializes requests; read in order to avoid competing for its local gate.
      const previous = await researchFetch<Result>(`runs/${run.id}`);
      const frozen = await researchFetch<FrozenProtocol>(`protocols/${run.protocol_id}`);
      const spec = frozen.request, p = spec.parameters, c = spec.config;
      setSymbol(previous.manifest.symbol); setInterval(previous.manifest.interval); setSelected(spec.dataset_hash);
      setStrategy(spec.strategy);
      setDates({ train_start: dateInput(spec.train_start), train_end: dateInput(spec.train_end),
        validation_end: dateInput(spec.validation_end), test_end: dateInput(spec.test_end) });
      setParameters({ fast: String(p.fast), slow: String(p.slow), rsi_period: String(p.rsi_period),
        rsi_entry: String(p.rsi_entry), rsi_exit: String(p.rsi_exit), lookback: String(p.lookback),
        stop_fraction: String(p.stop_fraction), target_fraction: String(p.target_fraction),
        max_atr_ratio: p.max_atr_ratio === null ? "" : String(p.max_atr_ratio),
        volume_multiple: p.volume_multiple === null ? "" : String(p.volume_multiple) });
      setEntry(p.trend_entry); setExit(p.trend_exit); setFilter(p.trend_filter);
      setCapital(c.capital); setRisk(c.risk_fraction); setExposure(c.exposure_fraction); setPolicy(c.final_policy);
      setFee(c.costs.fee_rate); setSlippage(c.costs.slippage_rate);
      setResult(previous); setProtocol(run.protocol_id); setPartition(run.partition); setTradePage(0); setEquityPage(0);
      setNotice("Protocolo anterior restaurado. Selecione a janela a executar; a configuração permanece congelada.");
    });
  }
  const matching = datasets.filter(d => d.symbol === symbol && d.interval === interval);
  const m = result?.simulation.metrics;
  const selectedDataset = datasets.find(d => d.dataset_id === selected);
  return <main id="main-content" className="page history-page backtest-page">
    <div className="page-heading"><div><h1>Backtesting</h1><p>Hipóteses, custos e resultados auditáveis. Pesquisa histórica offline.</p></div><span className="tag"><FlaskConical size={14}/>Simulação Spot</span></div>
    {error && <div className="data-alert" role="alert"><div><strong>Pesquisa interrompida</strong><p>{error}</p></div><Button variant="ghost" disabled={pending} onClick={load}>Atualizar catálogo</Button></div>}
    {notice && <p className="history-notice" role="status">{notice}</p>}
    <section className="panel history-request"><div className="panel-heading"><div><h2>Configurar experimento</h2><p>Parâmetros experimentais. Mack permanece não validada.</p></div><span className="tag">01 / Protocolo</span></div>
      <form onSubmit={e => { e.preventDefault(); void freeze(); }}>
        <fieldset disabled={pending || !!protocol}><legend className="sr-only">Dados e premissas do protocolo</legend>
          <div className="history-fields backtest-fields">
            <label>Ativo<select value={symbol} onChange={e => { setSymbol(e.target.value); setSelected(""); }}><option>BTCUSDT</option><option>ETHUSDT</option></select></label>
            <label>Timeframe<select value={interval} onChange={e => { setInterval(e.target.value); setSelected(""); }}><option value="15">15m</option><option value="60">1h</option><option value="240">4h</option><option value="D">1d</option></select></label>
            <label className="backtest-wide">Dataset aprovado<select required value={selected} onChange={e => choose(e.target.value)}><option value="">{loading ? "Carregando catálogo…" : "Selecione um dataset"}</option>{matching.map(d => <option key={d.dataset_id} value={d.dataset_id}>{timeframe(d.interval)} · {d.candle_count} candles · {d.dataset_id.slice(0,10)}</option>)}</select></label>
          </div>
          {!loading && !matching.length && <p className="backtest-note">Nenhum dataset aprovado para esta seleção. <Link href="/history" className="text-link">Solicitar dados históricos</Link></p>}
          {selectedDataset && <p className="backtest-note">Cobertura disponível: {utcTime(selectedDataset.start_time)} → {utcTime(selectedDataset.end_time)} UTC. Até 20.000 candles incluindo aquecimento.</p>}
          <div className="history-fields backtest-fields backtest-section">
            {Object.entries({ train_start:"Início do treino (UTC)", train_end:"Início da validação (UTC)", validation_end:"Início do teste (UTC)", test_end:"Fim exclusivo (UTC)" }).map(([key,label]) => <label key={key}>{label}<input type="datetime-local" required value={dates[key as keyof typeof dates]} onChange={e => setDates({...dates,[key]:e.target.value})}/></label>)}
          </div>
          <p className="backtest-note">Histórico anterior aquece indicadores. Cada janela reinicia o capital. Nenhum ajuste automático na amostra de teste.</p>
          <div className="history-fields backtest-fields backtest-section">
            <label>Estratégia<select value={strategy} onChange={e => setStrategy(e.target.value as StrategyId)}>{Object.entries(strategies).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label>
            <label>Capital virtual (USDT)<input required inputMode="decimal" value={capital} onChange={e => setCapital(e.target.value)}/></label>
            <label>Taxa por fill (fração)<input required inputMode="decimal" value={fee} onChange={e => setFee(e.target.value)}/></label>
            <label>Slippage (fração)<input required inputMode="decimal" value={slippage} onChange={e => setSlippage(e.target.value)}/></label>
            <label>Risco planejado (fração)<input required disabled={strategy === "buy_hold"} inputMode="decimal" value={risk} onChange={e => setRisk(e.target.value)}/></label>
            <label>Exposição máxima (fração)<input required inputMode="decimal" value={exposure} onChange={e => setExposure(e.target.value)}/></label>
            <label className="backtest-wide">Encerramento<select value={policy} onChange={e => setPolicy(e.target.value)}><option value="liquidate">Liquidar no fechamento final, com custos</option><option value="mark_to_market">Manter posição e marcar a mercado</option></select></label>
          </div>
          <p className="backtest-note">0,01 representa 1%. Use ponto nos campos decimais. Custos são hipóteses, sem consulta à conta.</p>
          {strategy !== "buy_hold" && <details className="backtest-details" open><summary>Parâmetros da estratégia · versão 1</summary><div className="history-fields backtest-fields">
            {(Object.keys(defaults) as (keyof typeof defaults)[]).filter(k => ["stop_fraction","target_fraction"].includes(k) ||
              (strategy === "trend" && ["fast","slow","max_atr_ratio"].includes(k)) ||
              (strategy === "rsi" && ["rsi_period","rsi_entry","rsi_exit","slow"].includes(k)) ||
              (strategy === "breakout" && ["lookback","volume_multiple"].includes(k))).map(k => <label key={k}>{labels[k]}<input inputMode="decimal" value={parameters[k]} onChange={e => setParameters({...parameters,[k]:e.target.value})}/></label>)}
            {strategy === "trend" && <><label>Entrada Trend<select value={entry} onChange={e => setEntry(e.target.value)}><option value="cross">Cruzamento ascendente</option><option value="state">Estado acima da média lenta</option></select></label><label>Saída Trend<select value={exit} onChange={e => setExit(e.target.value)}><option value="averages">Rápida ≤ lenta</option><option value="close_fast">Fechamento abaixo da rápida</option></select></label></>}
            {strategy === "rsi" && <label>Filtro de tendência<select value={String(filter)} onChange={e => setFilter(e.target.value === "true")}><option value="false">Sem filtro</option><option value="true">Fechamento acima da SMA lenta</option></select></label>}
          </div><p className="backtest-note">Relação alvo / stop planejada: {number(String(Number(parameters.target_fraction)/Number(parameters.stop_fraction)))}. Gaps podem exceder a perda planejada.</p></details>}
          {strategy === "buy_hold" && <p className="backtest-note">Compra única na abertura após o primeiro fechamento elegível. Sem stop/alvo; risco por stop não se aplica ao benchmark.</p>}
        </fieldset>
        <div className="history-form-foot"><p>{protocol ? "Configuração congelada" : "Congele as regras antes de observar os resultados."}<span>Mesmo dataset, configuração e código produzem o mesmo hash.</span></p>{protocol ? <Button type="button" variant="outline" disabled={pending} onClick={() => {setProtocol("");setNotice("");}}>Nova configuração</Button> : <Button type="submit" disabled={pending || !selected || loading}><LockKeyhole size={14}/>Congelar protocolo</Button>}</div>
      </form>
    </section>
    {protocol && <section className="panel"><div className="panel-heading"><h2>Executar janela cronológica</h2><span className="tag">02 / Replay</span></div><p className="history-full-hash">Protocolo {protocol}</p><div className="backtest-actions history-fields"><label>Janela<select disabled={pending} value={partition} onChange={e => setPartition(e.target.value as Partition)}>{Object.entries(partitions).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label><Button disabled={pending} onClick={execute}><Play size={14}/>{pending ? "Processando…" : "Executar backtest"}</Button></div></section>}
    {result && m && <>
      <section className="panel"><div className="panel-heading"><div><h2>Resultado · {strategies[result.manifest.strategy]}</h2><p>{result.manifest.symbol} · {partitions[result.manifest.partition]} · {utcTime(result.manifest.start_time)} → {utcTime(result.manifest.end_time)} UTC</p></div><span className="tag">03 / Evidência</span></div>
        <div className="backtest-metrics">{[["Retorno líquido",`${number(m.net_return_pct)}%`],["PnL (USDT)",number(m.pnl)],["Drawdown máximo",`${number(m.max_drawdown_pct)}%`],["Trades encerrados",String(m.closed_trades)],
          ["Patrimônio final (USDT)",number(m.final_equity)],["Profit factor",number(m.profit_factor)],["Acerto",m.win_rate_pct === null ? "Indefinido" : `${number(m.win_rate_pct)}%`],["Expectativa / trade (USDT)",number(m.expectancy)],
          ["Taxas (USDT)",number(m.fees)],["Slippage (USDT)",number(m.slippage_cost)],["Exposição por candle",`${number(m.exposure_pct)}%`],["Diferença vs. Buy & Hold",`${number(result.excess_return_pp)} pp`]].map(([label,value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
        <div className="backtest-notes">{result.warnings.map(w => <p key={w}>{w}</p>)}{Object.entries(m.undefined).map(([k,v]) => <p key={k}>{k}: {v}.</p>)}<p>Ganhos / perdas / empates: {m.wins} / {m.losses} / {m.breakeven}. Relação ganho/perda realizada: {number(m.realized_win_loss_ratio)}. Custos totais: {number(m.total_costs)} USDT.</p><p>Saldo: {number(result.simulation.portfolio.cash)} USDT. Posição aberta: {result.simulation.portfolio.position ? `${result.simulation.portfolio.position.quantity} unidades` : "nenhuma"}.</p></div>
      </section>
      <section className="panel"><div className="panel-heading"><h2>Patrimônio e drawdown</h2><span className="tag">USDT · UTC</span></div><EquityChart result={result}/><p className="backtest-note backtest-pad">Azul: estratégia · Dourado: Buy & Hold ({number(result.benchmark.metrics.net_return_pct)}%) · Rosa: drawdown. Marcação no fechamento. <a className="text-link" href="https://www.tradingview.com/lightweight-charts/" target="_blank" rel="noreferrer">Lightweight Charts</a></p>
        <details className="backtest-details backtest-pad"><summary>Tabela de patrimônio (valores exatos)</summary><div className="table-scroll"><table><thead><tr><th>UTC</th><th>Patrimônio</th><th>Saldo</th><th>Quantidade</th><th>Drawdown %</th></tr></thead><tbody>{result.simulation.equity.slice(equityPage*25,(equityPage+1)*25).map(p => <tr key={p.time}><td>{utcTime(p.time)}</td><td>{p.equity}</td><td>{p.cash}</td><td>{p.quantity}</td><td>{p.drawdown_pct}</td></tr>)}</tbody></table></div><Pagination page={equityPage} count={result.simulation.equity.length} setPage={setEquityPage}/></details>
      </section>
      <section className="panel"><div className="panel-heading"><h2>Operações encerradas</h2><span className="tag">{m.closed_trades} trades</span></div>{!result.simulation.trades.length ? <div className="history-empty"><strong>Nenhum trade encerrado</strong><p>Consulte posição aberta, fills e justificativas no registro da execução.</p></div> : <><div className="table-scroll"><table><thead><tr><th>Entrada / saída UTC</th><th>Quantidade</th><th>Preços efetivos</th><th>Stop / alvo planejados</th><th>Taxas entrada / saída</th><th>PnL líquido USDT</th><th>Saída</th></tr></thead><tbody>{result.simulation.trades.slice(tradePage*25,(tradePage+1)*25).map((t,i) => <tr key={i}><td>{utcTime(t.entry.time)}<span className="history-cell-sub">{utcTime(t.exit.time)}</span></td><td>{t.entry.quantity}</td><td>{number(t.entry.price,4)} / {number(t.exit.price,4)}</td><td>{number(t.planned_stop)} / {number(t.planned_target)}</td><td>{number(t.entry.fee,4)} / {number(t.exit.fee,4)}</td><td>{number(t.pnl,4)}</td><td>{t.exit.reason}</td></tr>)}</tbody></table></div><Pagination page={tradePage} count={m.closed_trades} setPage={setTradePage}/></>}
        <details className="backtest-details backtest-pad"><summary>Fills, planos e recusas ({result.simulation.fills.length} fills)</summary><pre>{JSON.stringify({ fills: result.simulation.fills, plans: result.simulation.plans, rejections: result.simulation.rejections },null,2)}</pre></details>
      </section>
      <section className="panel"><div className="panel-heading"><h2>Reprodutibilidade</h2><Button variant="outline" disabled={pending} onClick={() => action(async () => { const v = await researchFetch<{identical:boolean}>(`runs/${result.id}/verify`,{}); setNotice(v.identical ? "Reexecução idêntica: hash confirmado." : "Divergência detectada na reexecução."); })}><RefreshCw size={14}/>Verificar hash</Button></div><p className="history-full-hash">Execução {result.id}</p><p className="history-full-hash">Dataset {result.manifest.dataset_hash}</p><details className="backtest-details backtest-pad"><summary>Manifesto e configurações utilizados</summary><pre>{JSON.stringify(result.manifest,null,2)}</pre></details></section>
    </>}
    {!result && <section className="panel history-empty"><FlaskConical size={26}/><strong>Nenhum resultado selecionado</strong><p>Selecione dados aprovados e congele um protocolo, ou consulte uma execução anterior. Nenhum resultado demonstrativo é fornecido.</p></section>}
    <section className="panel"><div className="panel-heading"><h2>Execuções anteriores</h2><Button variant="ghost" disabled={pending || loading} onClick={load}>Atualizar</Button></div>{!runs.length ? <div className="history-empty"><p>{loading ? "Consultando execuções…" : "Nenhuma execução persistida."}</p></div> : <div className="table-scroll"><table><thead><tr><th>Execução SHA-256</th><th>Janela</th><th>Registro UTC</th><th>Resultado / protocolo</th></tr></thead><tbody>{runs.map(run => <tr key={run.id}><td title={run.id}>{run.id.slice(0,16)}…</td><td>{partitions[run.partition]}</td><td>{run.created_at}</td><td><Button variant="ghost" disabled={pending} onClick={() => action(async () => {setResult(await researchFetch<Result>(`runs/${run.id}`));setTradePage(0);setEquityPage(0);setNotice("Resultado histórico carregado; configurações no manifesto.");})}>Consultar</Button><Button variant="ghost" disabled={pending} onClick={() => resume(run)}>Retomar protocolo</Button></td></tr>)}</tbody></table></div>}</section>
  </main>;
}

function Pagination({page,count,setPage}: {page:number;count:number;setPage:(n:number)=>void}) {
  return <div className="backtest-pagination"><Button variant="ghost" disabled={!page} onClick={() => setPage(page-1)}>Anterior</Button><span>{page+1} / {Math.max(1,Math.ceil(count/25))}</span><Button variant="ghost" disabled={(page+1)*25 >= count} onClick={() => setPage(page+1)}>Próxima</Button></div>;
}
