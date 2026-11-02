"use client";

import { useEffect, useRef } from "react";
import { ColorType, createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import type { Result } from "@/lib/research";

export function EquityChart({ result }: { result: Result }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!host.current) return;
    const chart = createChart(host.current, { autoSize: true, height: 380,
      layout: { background: { type: ColorType.Solid, color: "#101924" }, textColor: "#9aaabd", attributionLogo: true },
      grid: { vertLines: { visible: false }, horzLines: { color: "#223044" } },
      timeScale: { timeVisible: true, borderVisible: false }, rightPriceScale: { borderVisible: false },
      localization: { locale: "pt-BR", timeFormatter: (time: number) => new Date(time*1000).toISOString().replace("T", " ").slice(0,16)+" UTC" },
    });
    chart.addSeries(LineSeries, { color: "#8bb9fb", lineWidth: 2, title: "Patrimônio" }).setData(
      result.simulation.equity.map(p => ({ time: p.time as UTCTimestamp, value: Number(p.equity) })));
    chart.addSeries(LineSeries, { color: "#e8bf7d", lineWidth: 1, title: "Buy & Hold" }).setData(
      result.benchmark.equity.map(p => ({ time: p.time as UTCTimestamp, value: Number(p.equity) })));
    chart.addSeries(LineSeries, { color: "#f29399", lineWidth: 1, title: "Drawdown %" }, 1).setData(
      result.simulation.equity.map(p => ({ time: p.time as UTCTimestamp, value: -Number(p.drawdown_pct) })));
    chart.panes()[1].setHeight(100);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [result]);
  return <div ref={host} className="backtest-chart" role="img" aria-label="Patrimônio simulado, Buy & Hold e drawdown. Eixo UTC; dados completos na tabela de patrimônio." />;
}
