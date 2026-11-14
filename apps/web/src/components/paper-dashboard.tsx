"use client";
import { useMemo, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { WalletTable, PositionTable, FillTable, SignalTables } from "@/components/paper-tables";
import { WalletDetail } from "@/components/paper-detail";
import { date, money, type Decision, type Event, type Fill, type Overview, type Page, type Point, type Signal, type Wallet } from "@/lib/paper";
import { usePaperResource } from "@/hooks/use-paper-resource";

export function PaperDashboard() {
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState(""); const [filter, setFilter] = useState("all"); const [sort, setSort] = useState("bot"); const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const o = usePaperResource<Overview>("overview", refresh);
  const s = usePaperResource<Signal[]>("signals", refresh);
  const d = usePaperResource<Decision[]>("decisions", refresh);
  const root = selected ? `wallets/${selected}` : null;
  const w = usePaperResource<Wallet>(root, refresh);
  const f = usePaperResource<Page<Fill>>(root ? `${root}/fills?limit=10&offset=${offset}` : null, refresh);
  const e = usePaperResource<Page<Event>>(root ? `${root}/events?limit=10` : null, refresh);
  const p = usePaperResource<{items:Point[]}>(root ? `${root}/equity` : null, refresh);
  const overview = o.data;
  const detailsFailed = !!selected && !!(w.error || f.error || e.error || p.error);
  const detailsLoading = !!selected && (w.loading || f.loading || e.loading || p.loading);
  const detailsUncertain = detailsFailed || detailsLoading;
  const wallet = detailsFailed || detailsLoading ? null : w.data;
  const fills = detailsFailed || detailsLoading ? null : f.data;
  const visible = useMemo(() => (overview?.wallets ?? []).filter(w => `${w.spec.bot_id} ${w.spec.symbol} ${w.spec.strategy}`.toLowerCase().includes(search.toLowerCase()) && (filter === "all" || w.state.state === filter)).sort((a,b) => (sort === "symbol" ? a.spec.symbol.localeCompare(b.spec.symbol) : a.spec.bot_id.localeCompare(b.spec.bot_id))),[overview,search,filter,sort]);
  const summary=overview?.summary;
  return <main id="main-content" className="page paper-page"><div className="page-heading"><div><span className="paper-eyebrow">OBSERVABILIDADE · AMBIENTE LOCAL</span><h1>Paper Trading</h1><p>Carteiras e decisões em um único lugar.</p></div><Button variant="outline" onClick={() => setRefresh(x => x+1)}><RefreshCw size={14}/>Atualizar</Button></div>
    <div className="paper-banner"><ShieldCheck size={19}/><div><strong>PAPER TRADING — SALDOS FICTÍCIOS</strong><p>Somente leitura · nenhuma operação real ou virtual é executada nesta tela.</p></div></div>
    {[["Resumo",o.error],["Sinais",s.error],["Decisões",d.error],["Carteira",w.error],["Fills",f.error],["Eventos",e.error],["Equity",p.error]].filter(([,error]) => error).map(([name,error]) => <div key={name} className="data-alert" role="alert"><div><strong>{name}: consulta indisponível</strong><p>{error} Use Atualizar para tentar novamente.</p></div></div>)}
    {!overview && !o.error && <div className="panel paper-empty" aria-busy="true">Carregando dados paper…</div>}
    {summary && <><div className="paper-meta"><span>Interface atualizada: {o.observed ? date(o.observed/1000) : "Indisponível"}</span><span>{detailsUncertain ? "Integridade da carteira selecionada: desconhecida" : summary.integrity === "WALLETS_VERIFIED" ? "Ledgers consultados verificados" : "Integridade dos ledgers indisponível"}</span><span>Monitor: estado desconhecido</span></div>
      {!detailsUncertain && <section className="paper-metrics" aria-label="Resumo financeiro fictício">{[["Capital inicial",money(summary.initial_capital)],["Saldo disponível",money(summary.cash)],["Patrimônio marcado",money(summary.equity)],["Exposição nocional",money(summary.position_value)],["PnL realizado",money(summary.realized_pnl)],["PnL não realizado",money(summary.unrealized_pnl)],["PnL total",money(summary.total_pnl)],["Carteiras / posições",`${summary.wallets} / ${summary.positions}`],["Fills / decisões",`${summary.fills} / ${summary.decisions}`]].map(([label,value]) => <div className="panel paper-metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</section>}
      <section className="panel paper-panel"><div className="panel-heading"><div><h2>Saúde dos dados</h2><p>Horários de origem, não horário de carregamento</p></div></div><div className="paper-health">{overview?.markets.map(m => <div key={m.symbol}><strong>{m.symbol}</strong><span>{m.status === "HEALTHY" ? "Atualizado" : m.status === "STALE" ? "Obsoleto" : "Indisponível"} · {m.source_time_ms ? date(m.source_time_ms/1000) : "sem coleta"}</span></div>)}<div><strong>Última coleta completa</strong><span>{overview?.collection?.last_success_ms ? date(overview.collection.last_success_ms/1000) : "Indisponível"}</span></div><div><strong>Erro da coleta</strong><span>{overview?.collection?.error_code ?? "Nenhum informado"}</span></div></div></section>
      <div className="paper-filters"><label>Buscar carteira <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Bot, ativo ou estratégia" /></label><label>Estado <select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Todas</option><option value="active">Ativas</option><option value="paused">Pausadas</option></select></label><label>Ordenar <select value={sort} onChange={e => setSort(e.target.value)}><option value="bot">Bot</option><option value="symbol">Ativo</option></select></label></div>
      <WalletTable wallets={visible.filter(item => !detailsUncertain || item.wallet_id !== selected)} selected={selected} onSelect={id => {setSelected(id);setOffset(0);}}/>
      {!detailsUncertain && <PositionTable wallets={overview?.wallets ?? []}/>}
      {detailsLoading && <div className="panel paper-empty" aria-busy="true">Carregando carteira selecionada…</div>}
      {wallet && <WalletDetail wallet={wallet} events={e.data?.items ?? []} points={p.data?.items ?? []}/>}
      {selected && fills && <><FillTable fills={fills.items}/><div className="paper-pagination"><button disabled={offset===0} onClick={() => setOffset(Math.max(0,offset-10))}>Anterior</button><span>{fills.total} fills · página {Math.floor(offset/10)+1}</span><button disabled={offset+10>=fills.total} onClick={() => setOffset(offset+10)}>Próxima</button></div></>}
      {s.data && d.data && <SignalTables signals={s.data} decisions={d.data}/>}</>}
  </main>;
}
