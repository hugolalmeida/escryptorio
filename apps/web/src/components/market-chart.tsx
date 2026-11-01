"use client";

import { useEffect, useRef } from "react";
import { CandlestickSeries, ColorType, createChart, CrosshairMode, HistogramSeries, LineSeries,
  type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import type { Market } from "@/lib/market";

export function MarketChart({ data, mode, averages }: { data: Market; mode: "candles" | "line"; averages: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<{ chart: IChartApi; main: ISeriesApi<"Candlestick"> | ISeriesApi<"Line">;
    volume: ISeriesApi<"Histogram">; sma?: ISeriesApi<"Line">; ema?: ISeriesApi<"Line">; fitted: boolean } | null>(null);
  useEffect(() => {
    if (!host.current) return;
    const chart = createChart(host.current, {
      autoSize: true, height: 398,
      layout: { background: { type: ColorType.Solid, color: "#101924" }, textColor: "#93a3b7", fontFamily: "Segoe UI, sans-serif", fontSize: 11,
        attributionLogo: true, panes: { separatorColor: "#223044", separatorHoverColor: "#33465e" } },
      grid: { vertLines: { visible: false }, horzLines: { color: "#1c2838" } },
      rightPriceScale: { borderVisible: false, minimumWidth: 74 },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false, rightOffset: 5, barSpacing: 7 },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: "#536981", labelBackgroundColor: "#31445b" }, horzLine: { color: "#536981", labelBackgroundColor: "#31445b" } },
      localization: { locale: "pt-BR", timeFormatter: (time: number) => new Intl.DateTimeFormat("pt-BR", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }).format(time * 1000) + " UTC" },
    });
    const main = mode === "candles" ? chart.addSeries(CandlestickSeries, { upColor: "#48cba3", downColor: "#e98085",
      borderVisible: false, wickUpColor: "#48cba3", wickDownColor: "#e98085" })
      : chart.addSeries(LineSeries, { color: "#73a9f9", lineWidth: 2 });
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false }, 1);
    chart.panes()[1].setHeight(82);
    const sma = averages ? chart.addSeries(LineSeries, { color: "#d5b679", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }) : undefined;
    const ema = averages ? chart.addSeries(LineSeries, { color: "#7e9cdd", lineWidth: 1, priceLineVisible: false, lastValueVisible: false }) : undefined;
    chartRef.current = { chart, main, volume, sma, ema, fitted: false };
    return () => { chart.remove(); chartRef.current = null; };
  }, [mode, averages]);
  useEffect(() => {
    const refs = chartRef.current;
    if (!refs) return;
    if (mode === "candles") (refs.main as ISeriesApi<"Candlestick">).setData(data.candles.map(c => ({ time: c.time as UTCTimestamp,
      open: Number(c.open), high: Number(c.high), low: Number(c.low), close: Number(c.close) })));
    else (refs.main as ISeriesApi<"Line">).setData(data.candles.map(c => ({ time: c.time as UTCTimestamp, value: Number(c.close) })));
    refs.volume.setData(data.candles.map(c => ({ time: c.time as UTCTimestamp, value: Number(c.volume),
      color: Number(c.close) >= Number(c.open) ? "#48cba34a" : "#e980854a" })));
    refs.sma?.setData(data.indicators.sma_20.map(p => ({ time: p.time as UTCTimestamp, value: Number(p.value) })));
    refs.ema?.setData(data.indicators.ema_50.map(p => ({ time: p.time as UTCTimestamp, value: Number(p.value) })));
    if (!refs.fitted) {
      refs.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, data.candles.length - 95), to: data.candles.length + 4 });
      refs.fitted = true;
    }
  }, [data, mode, averages]);
  return <div className="chart-host" ref={host} role="img" aria-label={`Gráfico ${mode === "candles" ? "de candles" : "de linha"} de ${data.symbol}, com volume. Eixo de tempo em UTC. Valores disponíveis no resumo de mercado.`} />;
}
