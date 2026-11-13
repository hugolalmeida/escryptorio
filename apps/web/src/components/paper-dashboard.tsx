"use client";
import { useEffect, useMemo, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { WalletTable, PositionTable, FillTable, SignalTables } from "@/components/paper-tables";
import { WalletDetail } from "@/components/paper-detail";
import { date, money, paperGet, type Decision, type Event, type Fill, type Overview, type Page, type Point, type Signal, type Wallet } from "@/lib/paper";

export function PaperDashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]); const [decisions, setDecisions] = useState<Decision[]>([]);
  const [selected, setSelected] = useState<string | null>(null); const [wallet, setWallet] = useState<Wallet | null>(null);
  const [fills, setFills] = useState<Page<Fill> | null>(null); const [events, setEvents] = useState<Event[]>([]); const [points, setPoints] = useState<Point[]>([]);
  const [search, setSearch] = useState(""); const [filter, setFilter] = useState("all"); const [sort, setSort] = useState("bot"); const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null); const [updated, setUpdated] = useState<number | null>(null); const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const [o,s,d] = await Promise.all([paperGet<Overview>("overview",controller.signal),paperGet<Signal[]>("signals",controller.signal),paperGet<Decision[]>("decisions",controller.signal)]);
        if (!controller.signal.aborted) { setOverview(o.data); setSignals(s.data); setDecisions(d.data); setUpdated(o.observed_at_ms); setError(null); }
      } catch { if (!controller.signal.aborted) { setError("Backend indisponível ou integridade não pôde ser verificada."); setOverview(null); } }
    };
    void load(); const timer = window.setInterval(load,15000);
    return () => { controller.abort(); window.clearInterval(timer); };
  },[refresh]);
  useEffect(() => {
    if (!selected) { setWallet(null); setFills(null); return; }
    const controller = new AbortController();
    const load = async () => {
      try {
        const root = `wallets/${selected}`;
        const [w,f,e,p] = await Promise.all([paperGet<Wallet>(root,controller.signal),paperGet<Page<Fill>>(`${root}/fills?limit=10&offset=${offset}`,controller.signal),paperGet<Page<Event>>(`${root}/events?limit=10`,controller.signal),paperGet<{items:Point[]}>(`${root}/equity`,controller.signal)]);
        if (!controller.signal.aborted) { setWallet(w.data); setFills(f.data); setEvents(e.data.items); setPoints(p.data.items); }
      } catch { if (!controller.signal.aborted) { setWallet(null); setFills(null); setError("Detalhes indisponíveis ou integridade não pôde ser verificada."); } }
    };
    void load(); const timer=window.setInterval(load,15000);
    return () => { controller.abort(); window.clearInterval(timer); };
  },[selected,offset,refresh]);
  const visible = useMemo(() => (overview?.wallets ?? []).filter(w => `${w.spec.bot_id} ${w.spec.symbol} ${w.spec.strategy}`.toLowerCase().includes(search.toLowerCase()) && (filter === "all" || w.state.state === filter)).sort((a,b) => (sort === "symbol" ? a.spec.symbol.localeCompare(b.spec.symbol) : a.spec.bot_id.localeCompare(b.spec.bot_id))),[overview,search,filter,sort]);
  const summary=overview?.summary;
  return <main id="main-content" className="page paper-page"><div className="page-heading"><div><span className="paper-eyebrow">OBSERVABILIDADE · AMBIENTE LOCAL</span><h1>Paper Trading</h1><p>Carteiras e decisões em um único lugar.</p></div><Button variant="outline" onClick={() => setRefresh(x => x+1)}><RefreshCw size={14}/>Atualizar</Button></div>
    <div className="paper-banner"><ShieldCheck size={19}/><div><strong>PAPER TRADING — SALDOS FICTÍCIOS</strong><p>Somente leitura · nenhuma operação real ou virtual é executada nesta tela.</p></div></div>
    {error && <div className="data-alert" role="alert"><div><strong>Consulta indisponível</strong><p>{error}</p></div></div>}
    {!overview && !error && <div className="panel paper-empty" aria-busy="true">Carregando dados paper…</div>}
    {summary && <><div className="paper-meta"><span>Interface atualizada: {updated ? date(updated/1000) : "Indisponível"}</span><span>Integridade das carteiras: {summary.integrity === "WALLETS_VERIFIED" ? "verificada" : "indisponível"}</span><span>Monitor: estado desconhecido</span></div>
      <section className="paper-metrics" aria-label="Resumo financeiro fictício">{[["Capital inicial",money(summary.initial_capital)],["Saldo disponível",money(summary.cash)],["Patrimônio marcado",money(summary.equity)],["Exposição nocional",money(summary.position_value)],["PnL realizado",money(summary.realized_pnl)],["PnL não realizado",money(summary.unrealized_pnl)],["PnL total",money(summary.total_pnl)],["Carteiras / posições",`${summary.wallets} / ${summary.positions}`],["Fills / decisões",`${summary.fills} / ${summary.decisions}`]].map(([label,value]) => <div className="panel paper-metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</section>
      <section className="panel paper-panel"><div className="panel-heading"><div><h2>Saúde dos dados</h2><p>Horários de origem, não horário de carregamento</p></div></div><div className="paper-health">{overview?.markets.map(m => <div key={m.symbol}><strong>{m.symbol}</strong><span>{m.status === "HEALTHY" ? "Atualizado" : m.status === "STALE" ? "Obsoleto" : "Indisponível"} · {m.source_time_ms ? date(m.source_time_ms/1000) : "sem coleta"}</span></div>)}<div><strong>Última coleta completa</strong><span>{overview?.collection?.last_success_ms ? date(overview.collection.last_success_ms/1000) : "Indisponível"}</span></div><div><strong>Erro da coleta</strong><span>{overview?.collection?.error_code ?? "Nenhum informado"}</span></div></div></section>
      <div className="paper-filters"><label>Buscar carteira <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Bot, ativo ou estratégia" /></label><label>Estado <select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Todas</option><option value="active">Ativas</option><option value="paused">Pausadas</option></select></label><label>Ordenar <select value={sort} onChange={e => setSort(e.target.value)}><option value="bot">Bot</option><option value="symbol">Ativo</option></select></label></div>
      <WalletTable wallets={visible} selected={selected} onSelect={id => {setSelected(id);setOffset(0);}}/>
      <PositionTable wallets={overview?.wallets ?? []}/>
      {wallet && <WalletDetail wallet={wallet} events={events} points={points}/>}
      {selected && fills && <><FillTable fills={fills.items}/><div className="paper-pagination"><button disabled={offset===0} onClick={() => setOffset(Math.max(0,offset-10))}>Anterior</button><span>{fills.total} fills · página {Math.floor(offset/10)+1}</span><button disabled={offset+10>=fills.total} onClick={() => setOffset(offset+10)}>Próxima</button></div></>}
      <SignalTables signals={signals} decisions={decisions}/></>}
  </main>;
}
