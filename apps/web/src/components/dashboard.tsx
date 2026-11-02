"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowDownRight, ArrowRight, ArrowUpRight, ChartCandlestick, ChartNoAxesCombined, Check,
  ChevronRight, CircleAlert, Database, LockKeyhole, RefreshCw, ShieldCheck, SlidersHorizontal, Timer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarketChart } from "@/components/market-chart";
import { useMarket } from "@/hooks/use-market";
import { clock, compact, datetime, INTERVALS, price, SYMBOLS, type Interval, type Market, type SymbolName } from "@/lib/market";

function Change({ value }: { value?: string }) {
  if (value === undefined) return <span className="muted">—</span>;
  const positive = Number(value) >= 0;
  return <span className={`change ${positive ? "positive" : "negative"}`}>{positive ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}{positive ? "+" : ""}{price(Number(value) * 100)}%</span>;
}

const strategyRows = [
  ["Trend", "Tendência por médias móveis", "Em pesquisa"],
  ["RSI", "Reversão à média", "Em pesquisa"],
  ["Breakout", "Rompimento de faixa", "Em pesquisa"],
  ["Buy & Hold", "Referência de mercado", "Em pesquisa"],
  ["Mack", "Metodologia a especificar", "Não validada"],
];

export function Dashboard() {
  const [symbol, setSymbol] = useState<SymbolName>("BTCUSDT");
  const [interval, setInterval] = useState<Interval>("60");
  const [mode, setMode] = useState<"candles" | "line">("candles");
  const [averages, setAverages] = useState(true);
  const { entries, reload, now } = useMarket(interval);
  const entry = entries[`${symbol}:${interval}`];
  const data = entry?.data;
  const age = data ? Math.max(0, Math.floor((now - data.source_time_ms) / 1000)) : 0;
  const clockSkew = data ? now < data.source_time_ms - 5000 : false;
  const stale = !!data && (data.stale || age > data.stale_after_seconds || clockSkew || !!entry?.error);
  const loading = !entry || entry.loading;
  const last = data?.candles.at(-1);
  const indicator = data?.indicators;
  const trend = stale ? "Dados obsoletos" : indicator ? ({ alta: "Tendência de alta", baixa: "Tendência de baixa", neutra: "Sem tendência definida", insuficiente: "Histórico insuficiente" })[indicator.trend] : "Aguardando dados";
  const stateLabel = data ? stale ? "Dados obsoletos" : "Dados atualizados" : entry?.error ? "Coleta indisponível" : "Conectando à coleta";
  return <main id="main-content" className="page dashboard">
    <div className="page-heading"><div><h1>Visão de mercado</h1><p>Observe o mercado. Construa sua próxima hipótese.</p></div><div className="heading-actions"><span className={`feed-status ${stale || entry?.error ? "status-warning" : data ? "status-good" : ""}`}><i />{stateLabel}</span><Button variant="outline" onClick={reload} disabled={loading}><RefreshCw size={14} className={loading ? "spin" : ""} />Atualizar</Button></div></div>

    <section className="asset-grid" aria-label="Ativos monitorados">{SYMBOLS.map(asset => {
      const assetEntry = entries[`${asset}:${interval}`];
      const market = assetEntry?.data;
      const assetStale = !!market && (market.stale || now - market.source_time_ms > market.stale_after_seconds * 1000 || now < market.source_time_ms - 5000 || !!assetEntry?.error);
      return <button key={asset} className={`asset-card ${symbol === asset ? "asset-selected" : ""}`} onClick={() => setSymbol(asset)} aria-pressed={symbol === asset}>
        <div className="asset-top"><div className="asset-name"><span className={`coin-mark ${asset === "BTCUSDT" ? "coin-btc" : "coin-eth"}`}>{asset === "BTCUSDT" ? "B" : "E"}</span><div><strong>{asset === "BTCUSDT" ? "Bitcoin" : "Ethereum"}</strong><small>{asset.replace("USDT", " / USDT")}<span>SPOT</span></small></div></div><span className="asset-choice">{symbol === asset ? <Check size={14} /> : <ChevronRight size={15} />}</span></div>
        <div className="asset-price"><span>{price(market?.ticker.price)}<small>USDT</small></span><Change value={market?.ticker.change_24h} /></div>
        <div className="asset-bottom"><span>Variação em 24 horas</span><span>{assetStale ? "Obsoleto" : market ? `Bybit · ${clock(market.source_time_ms)}` : assetEntry?.error ? "Indisponível" : "Aguardando coleta"}</span></div>
      </button>;
    })}</section>

    {entry?.error && <div className="data-alert" role="alert" aria-label="Atualização de mercado"><CircleAlert size={17} /><div><strong>Atualização interrompida</strong><p>{entry.error}{data ? " O último snapshot permanece visível com seu horário original." : " Nenhum preço foi substituído por dados simulados."}</p></div><Button variant="ghost" size="sm" onClick={reload} disabled={loading}>Tentar novamente</Button></div>}
    {stale && !entry?.error && <div className="data-alert" role="status"><Timer size={17} /><div><strong>{clockSkew ? "Relógios fora de sincronia" : "A coleta precisa ser atualizada"}</strong><p>{clockSkew ? "Confira o relógio do Windows antes de usar os dados." : `O snapshot tem ${age}s. Verifique se o worker está em execução; o limite é ${data?.stale_after_seconds}s.`}</p></div></div>}

    <div className="market-layout"><section className="panel chart-panel" aria-label="Histórico de preços"><div className="panel-heading"><div className="chart-title"><h2>{symbol.replace("USDT", " / USDT")}</h2><span className="tag">Bybit Spot</span></div><span className="muted tiny">Preço em USDT</span></div>
      <div className="chart-toolbar"><div className="segmented" aria-label="Período">{INTERVALS.map(i => <button key={i.value} aria-pressed={interval === i.value} className={interval === i.value ? "selected" : ""} onClick={() => setInterval(i.value)}>{i.label}</button>)}</div><div className="chart-tools"><div className="segmented"><button title="Candles" aria-label="Exibir candles" aria-pressed={mode === "candles"} className={mode === "candles" ? "selected" : ""} onClick={() => setMode("candles")}><ChartCandlestick size={15} /></button><button title="Linha" aria-label="Exibir linha" aria-pressed={mode === "line"} className={mode === "line" ? "selected" : ""} onClick={() => setMode("line")}><ChartNoAxesCombined size={15} /></button></div><button className={`indicator-toggle ${averages ? "toggle-active" : ""}`} aria-label="Médias" aria-pressed={averages} onClick={() => setAverages(!averages)}><SlidersHorizontal size={13} /><span>Médias</span></button></div></div>
      <div className="ohlc-row" aria-label="Último candle"><span>A <b>{price(last?.open)}</b></span><span>M <b>{price(last?.high)}</b></span><span>m <b>{price(last?.low)}</b></span><span>F <b>{price(last?.close)}</b></span><span className="candle-status">{last ? last.closed ? "Fechado" : "Em formação" : "—"}</span></div>
      {data ? <MarketChart key={`${symbol}:${interval}`} data={data} mode={mode} averages={averages} /> : <div className="chart-empty" aria-busy={loading}>{entry?.error ? <CircleAlert size={30} /> : <ChartCandlestick size={32} />}<strong>{entry?.error ? "Sem dados de mercado" : "Preparando o gráfico"}</strong><p>{entry?.error ? "Aguardando uma coleta pública válida da Bybit." : "Buscando candles, volume e especificações do ativo."}</p>{entry?.error && <Button variant="outline" size="sm" onClick={reload} disabled={loading}>Consultar novamente</Button>}</div>}
      <div className="chart-caption"><div className="chart-legend"><span><i className="legend-volume" />Volume</span>{averages && <><span><i className="legend-sma" />SMA 20</span><span><i className="legend-ema" />EMA 50</span></>}</div><span>Eixo em UTC</span></div>
      <div className="chart-source"><span>Fonte: Bybit API v5 · {data?.candles.length ?? 0} candles</span><a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">Gráficos por TradingView <ArrowUpRight size={11} /></a></div>
    </section>

    <aside className="market-aside"><section className="panel"><div className="panel-heading"><h2>Leitura técnica</h2><span className="tag">{INTERVALS.find(i => i.value === interval)?.label}</span></div>
      <div className={`trend-reading ${!stale && indicator?.trend === "alta" ? "positive" : !stale && indicator?.trend === "baixa" ? "negative" : "muted"}`}><ChartNoAxesCombined size={19} /><strong>{trend}</strong></div>
      <div className="indicator-list"><div><span>SMA <small>20</small></span><strong>{price(indicator?.sma_20.at(-1)?.value)}</strong></div><div><span>EMA <small>50</small></span><strong>{price(indicator?.ema_50.at(-1)?.value)}</strong></div><div><span>RSI <small>14 · Wilder</small></span><strong>{price(indicator?.rsi_14)}</strong></div><div><span>ATR <small>14 · Wilder</small></span><strong>{price(indicator?.atr_14)}</strong></div></div>
      <p className="panel-note">Calculados sobre {indicator?.closed_candles ?? 0} candles fechados. {indicator?.as_of ? `Último fechamento: ${clock((indicator.as_of + (interval === "D" ? 86400 : Number(interval) * 60)) * 1000)}.` : "Aguardando histórico."} Leitura descritiva, sem sinal de entrada.</p>
    </section>
    <section className="panel"><div className="panel-heading"><h2>Mercado em 24h</h2><span className="muted tiny">{symbol.slice(0, 3)}</span></div><dl className="market-stats"><div><dt>Máxima</dt><dd>{price(data?.ticker.high_24h)}<small>USDT</small></dd></div><div><dt>Mínima</dt><dd>{price(data?.ticker.low_24h)}<small>USDT</small></dd></div><div><dt>Volume base</dt><dd>{compact(data?.ticker.volume_24h)}<small>{symbol.slice(0, 3)}</small></dd></div><div><dt>Volume financeiro</dt><dd>{compact(data?.ticker.turnover_24h)}<small>USDT</small></dd></div></dl></section>
    </aside></div>

    <div className="research-layout"><section className="panel strategy-panel"><div className="panel-heading"><div><h2>Laboratório de estratégias</h2><p>Uma base comum. Hipóteses diferentes.</p></div><Link href="/arena" className="text-link">Explorar Arena <ArrowRight size={14} /></Link></div><div className="table-scroll"><table><thead><tr><th>Estratégia</th><th>Abordagem</th><th>Validação</th><th className="numeric">Retorno líquido</th></tr></thead><tbody>{strategyRows.map(([name, description, state]) => <tr key={name}><td><span className="strategy-name"><i className={name === "Mack" ? "strategy-dot-unvalidated" : ""} />{name}</span></td><td className="muted">{description}</td><td><span className={`strategy-state ${name === "Mack" ? "unvalidated" : ""}`}>{state}</span></td><td className="numeric muted">—</td></tr>)}</tbody></table></div><div className="table-footnote">Resultados de pesquisa disponíveis em <Link href="/backtesting" className="text-link">Backtesting</Link>. Comparação na Arena ainda planejada.</div></section>
      <section className="panel provenance"><div className="panel-heading"><h2>Integridade dos dados</h2><Database size={15} className="muted" /></div><dl><div><dt>Última resposta Bybit</dt><dd>{data ? datetime(data.source_time_ms) : "Aguardando coleta"}</dd></div><div><dt>Idade do snapshot</dt><dd>{data ? `${age}s / limite ${data.stale_after_seconds}s` : "—"}</dd></div><div><dt>Dataset de candles fechados</dt><dd className="dataset-id" title={data?.dataset_id}>{data ? `sha256:${data.dataset_id.slice(0, 18)}…` : "—"}</dd></div></dl><div className="integrity-note"><ShieldCheck size={16} /><span>Coleta pública<small>Sem credenciais ou envio de ordens.</small></span><LockKeyhole size={13} /></div></section></div>
  </main>;
}
