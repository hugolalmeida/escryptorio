"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, CircleAlert, Database, Download, Fingerprint, Pause, Play, RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { INTERVALS, SYMBOLS, price, type Interval, type SymbolName } from "@/lib/market";
import { count, historyFetch, jobLabels, timeframe, utcTime, type Coverage, type DatasetManifest,
  type DatasetPreview, type HistoryJob } from "@/lib/history";

export function HistoryResearch() {
  const [symbol, setSymbol] = useState<SymbolName>("BTCUSDT");
  const [interval, setInterval] = useState<Interval>("60");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [jobs, setJobs] = useState<HistoryJob[]>([]);
  const [datasets, setDatasets] = useState<DatasetManifest[]>([]);
  const [coverage, setCoverage] = useState<{ key: string; data: Coverage }>();
  const [preview, setPreview] = useState<DatasetPreview>();
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const error = actionError || loadError;
  const [notice, setNotice] = useState("");
  useEffect(() => {
    const today = new Date();
    const last = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
    setEnd(last.toISOString().slice(0, 16));
    setStart(new Date(last.getTime()-30*86400000).toISOString().slice(0, 16));
  }, []);

  const startSeconds = Date.parse(`${start}Z`)/1000;
  const endSeconds = Date.parse(`${end}Z`)/1000;
  const step = interval === "D" ? 86400 : Number(interval)*60;
  const validRange = Number.isFinite(startSeconds) && Number.isFinite(endSeconds) && startSeconds >= 0 &&
    endSeconds > startSeconds && startSeconds % step === 0 && endSeconds % step === 0 && (endSeconds-startSeconds)/step <= 100000;
  const query = new URLSearchParams({ symbol, interval, start: `${start}:00Z`, end: `${end}:00Z` }).toString();
  const currentCoverage = coverage?.key === query ? coverage.data : undefined;
  const reload = useCallback(() => setRefresh(n => n+1), []);

  useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;
    const load = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]);
        const [jobData, datasetData, coverageData] = await Promise.all([
          historyFetch<{ jobs: HistoryJob[] }>("jobs", { signal }),
          historyFetch<{ datasets: DatasetManifest[] }>("datasets", { signal }),
          validRange ? historyFetch<Coverage>(`coverage?${query}`, { signal }) : Promise.resolve(undefined),
        ]);
        if (!controller.signal.aborted) {
          setJobs(jobData.jobs); setDatasets(datasetData.datasets);
          if (coverageData) setCoverage({ key: query, data: coverageData });
          setLoadError("");
        }
      } catch (e) {
        if (!controller.signal.aborted) setLoadError(e instanceof Error ? e.message : "Falha ao consultar o histórico.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
        inFlight = false;
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 3000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [query, validRange, refresh]);

  const action = async (perform: () => Promise<unknown>, message: string) => {
    setPending(true); setActionError(""); setNotice("");
    try { await perform(); setNotice(message); reload(); }
    catch (e) { setActionError(e instanceof Error ? e.message : "Falha na solicitação."); }
    finally { setPending(false); }
  };
  const collect = (event: React.FormEvent) => {
    event.preventDefault();
    if (!validRange) return;
    void action(() => historyFetch("jobs", { method: "POST", body: JSON.stringify({ symbol, interval,
      start: `${start}:00Z`, end: `${end}:00Z` }) }), "Solicitação persistida. O worker histórico coletará apenas as faixas ausentes.");
  };
  const verify = (id: string) => action(async () => {
    setPreview(undefined);
    setPreview(await historyFetch<DatasetPreview>(`datasets/${id}?limit=3`));
  }, "Hash e integridade do dataset verificados localmente, sem acessar a Bybit.");

  return <main id="main-content" className="page history-page">
    <div className="page-heading"><div><h1>Pesquisa histórica</h1><p>Dados verificáveis para hipóteses reproduzíveis.</p></div><Button variant="outline" onClick={reload} disabled={loading}><RefreshCw size={14} className={loading ? "spin" : ""} />Atualizar</Button></div>
    {error && <div className="data-alert" role="alert" aria-label="Erro na pesquisa"><CircleAlert size={17} /><div><strong>Não foi possível atualizar a pesquisa</strong><p>{error} Informações anteriores podem estar desatualizadas.</p></div></div>}
    {notice && <div className="history-notice" role="status"><Check size={15} />{notice}</div>}
    <section className="panel history-request"><div className="panel-heading"><h2>Solicitar histórico público</h2><span className="tag">Bybit Spot · UTC</span></div>
      <form onSubmit={collect}><div className="history-fields"><label>Ativo<select value={symbol} onChange={e => setSymbol(e.target.value as SymbolName)}>{SYMBOLS.map(s => <option key={s}>{s}</option>)}</select></label>
        <label>Timeframe<select value={interval} onChange={e => setInterval(e.target.value as Interval)}>{INTERVALS.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}</select></label>
        <label>Início UTC · inclusivo<input type="datetime-local" required step="60" value={start} onChange={e => setStart(e.target.value)} /></label>
        <label>Fim UTC · exclusivo<input type="datetime-local" required step="60" value={end} onChange={e => setEnd(e.target.value)} /></label></div>
        <div className="history-form-foot"><p>{validRange ? `${count((endSeconds-startSeconds)/step)} candles esperados. Limites alinhados em UTC.` : "Defina um período alinhado ao timeframe, com até 100.000 candles."}<span>Dados abertos são excluídos. Datas futuras permanecem incompletas até nova coleta.</span></p>
          <Button type="submit" variant="outline" disabled={!validRange || pending}><Download size={14} />{pending ? "Solicitando…" : "Solicitar coleta"}</Button></div></form>
    </section>

    <section className="panel history-coverage" aria-label="Cobertura do período"><div className="panel-heading"><h2>Cobertura disponível</h2><span className={`tag ${currentCoverage?.complete ? "positive" : ""}`}>{currentCoverage ? currentCoverage.complete ? "Completa" : "Incompleta" : loading ? "Consultando" : "Aguardando período válido"}</span></div>
      <div className="history-metrics"><div><span>Candles armazenados</span><strong>{currentCoverage ? count(currentCoverage.stored_count) : "—"}<small> / {currentCoverage ? count(currentCoverage.expected_count) : "—"}</small></strong></div><div><span>Cobertura validada</span><strong>{currentCoverage ? `${(currentCoverage.coverage_ratio*100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%` : "—"}</strong></div><div><span>Faixas ausentes</span><strong>{currentCoverage ? count(currentCoverage.gaps.length) : "—"}</strong></div></div>
      {currentCoverage && <progress className="history-progress" aria-label="Cobertura validada" value={currentCoverage.stored_count} max={currentCoverage.expected_count} />}
      {currentCoverage && currentCoverage.gaps.length > 0 && <div className="history-gap-list"><h3>Faixas ausentes · fim exclusivo</h3>{currentCoverage.gaps.slice(0, 8).map(g => <div key={g.start_time}><span>{utcTime(g.start_time)} → {utcTime(g.end_time)} UTC</span><span>{count(g.candle_count)} candles</span></div>)}{currentCoverage.gaps.length > 8 && <p>Exibindo 8 de {count(currentCoverage.gaps.length)} faixas. A API disponibiliza a lista completa.</p>}</div>}
      <div className="table-footnote">Cobertura usa somente o arquivo histórico validado. Snapshots do dashboard não contam como pesquisa aprovada. Nenhuma lacuna é preenchida artificialmente.</div>
    </section>

    <section className="panel history-jobs"><div className="panel-heading"><h2>Coletas e progresso</h2><span className="muted tiny">Atualização a cada 3s</span></div>
      {jobs.length === 0 ? <div className="history-empty"><Database size={24} /><strong>{loading ? "Consultando coletas" : "Nenhuma coleta solicitada"}</strong><p>Solicite um período para iniciar o arquivo de pesquisa. O worker histórico processa uma coleta por vez.</p></div> : <div className="table-scroll"><table><thead><tr><th>Mercado / período UTC</th><th>Progresso</th><th>Estado</th><th>Ação</th></tr></thead><tbody>{jobs.map(job => <tr key={job.id}><td><strong>{job.symbol} · {timeframe(job.interval)}</strong><span className="history-cell-sub">{utcTime(job.start_time)} → {utcTime(job.end_time)}</span><span className="history-cell-sub">ID {job.id.slice(0, 12)} · {job.pages} páginas · {job.runs.length} tentativas</span></td><td><span>{count(job.stored_count)} / {count(job.expected_count)}</span><progress aria-label={`Progresso ${job.symbol} ${job.id}`} value={job.stored_count} max={job.expected_count} /></td><td><span className={job.status === "completed" ? "positive" : ["failed", "incomplete"].includes(job.status) ? "history-warning" : "muted"}>{jobLabels[job.status]}</span>{job.error_code && <span className="history-cell-sub history-error-code">{job.error_code}</span>}{job.cancel_requested === 1 && job.status === "running" && <span className="history-cell-sub">Pausa solicitada</span>}</td><td>{["queued", "running"].includes(job.status) ? <Button variant="ghost" size="sm" disabled={pending || job.cancel_requested === 1} onClick={() => void action(() => historyFetch(`jobs/${job.id}/pause`, { method: "POST", body: "{}" }), "Pausa solicitada. As páginas confirmadas serão preservadas.")}><Pause size={12} />Pausar</Button> : job.status !== "completed" ? <Button variant="outline" size="sm" disabled={pending} onClick={() => void action(() => historyFetch(`jobs/${job.id}/resume`, { method: "POST", body: "{}" }), "Retomada enfileirada. Os candles já validados serão reutilizados.")}><Play size={12} />Retomar</Button> : <span className="positive"><Check size={15} aria-label="Coleta concluída" /></span>}</td></tr>)}</tbody></table></div>}
      <div className="table-footnote">Se o estado permanecer “Na fila”, inicie o worker histórico. Erros persistentes encerram a tentativa; retome após corrigir a causa. São exibidas as 50 coletas mais recentes.</div>
    </section>

    <section className="panel history-datasets"><div className="panel-heading"><h2>Datasets aprovados</h2><span className="tag"><ShieldCheck size={12} />Imutáveis · SHA-256</span></div>
      {datasets.length === 0 ? <div className="history-empty"><Fingerprint size={24} /><strong>Nenhum dataset aprovado</strong><p>A aprovação exige candles fechados e cobertura de 100%, sem lacunas. Datasets incompletos permanecem fora do motor quantitativo.</p></div> : <div className="table-scroll"><table><thead><tr><th>Dataset</th><th>Período UTC</th><th className="numeric">Candles</th><th>Integridade</th></tr></thead><tbody>{datasets.map(dataset => <tr key={dataset.dataset_id}><td><strong>{dataset.symbol} · {timeframe(dataset.interval)}</strong><span className="history-cell-sub dataset-id" title={dataset.dataset_id}>sha256:{dataset.dataset_id.slice(0, 18)}…</span></td><td>{utcTime(dataset.start_time)}<span className="history-cell-sub">até {utcTime(dataset.end_time)} · exclusivo</span></td><td className="numeric">{count(dataset.candle_count)}</td><td><Button variant="outline" size="sm" disabled={pending} onClick={() => void verify(dataset.dataset_id)}><Fingerprint size={13} />Verificar e consultar</Button></td></tr>)}</tbody></table></div>}
      {preview && <div className="history-preview" aria-label="Dataset verificado"><div className="history-verified"><ShieldCheck size={17} /><strong>Hash verificado · {count(preview.total_count)} candles disponíveis</strong></div><p className="history-full-hash">{preview.reference_hash}</p><dl><div><dt>Fonte</dt><dd>{preview.manifest.source} · {preview.manifest.market} · esquema v{preview.manifest.schema_version}</dd></div><div><dt>Coleta / aprovação UTC</dt><dd>{utcTime(Math.floor(preview.manifest.first_collected_at_ms/1000))} / {utcTime(Math.floor(preview.manifest.approved_at_ms/1000))}</dd></div><div><dt>Coletor</dt><dd>{preview.manifest.collector_version} · Pybit {preview.manifest.pybit_version}</dd></div></dl><div className="table-scroll"><table><caption>Prévia dos primeiros 3 candles · UTC · valores em USDT</caption><thead><tr><th>Abertura UTC</th><th className="numeric">Open</th><th className="numeric">High</th><th className="numeric">Low</th><th className="numeric">Close</th><th className="numeric">Volume base</th></tr></thead><tbody>{preview.candles.map(c => <tr key={c.time}><td>{utcTime(c.time)}</td>{[c.open, c.high, c.low, c.close, c.volume].map((value, index) => <td className="numeric" key={index}>{price(value, index === 4 ? 6 : 2)}</td>)}</tr>)}</tbody></table></div></div>}
      <div className="table-footnote">Datasets de pesquisa são separados dos snapshots e verificáveis offline. Esta fase prepara dados; estratégias, Arena e backtesting continuam planejados.</div>
    </section>
  </main>;
}
