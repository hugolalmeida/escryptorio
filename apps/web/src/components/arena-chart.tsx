"use client";

import { useEffect, useRef, useState } from "react";
import { ColorType, createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { colors, ids, type Runs } from "@/lib/arena";
import { number, strategies, type StrategyId } from "@/lib/research";

export function ArenaChart({ runs }: { runs: Runs }) {
  const host = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState<Record<StrategyId, boolean>>({ trend:true, rsi:true, breakout:true, buy_hold:true });
  const [hover, setHover] = useState<{ time: number; values: Partial<Record<StrategyId,number>> }>();
  useEffect(() => {
    if (!host.current) return;
    const chart = createChart(host.current, { autoSize:true, height:340,
      layout:{ background:{type:ColorType.Solid,color:"#101924"}, textColor:"#a5b6cd", attributionLogo:true },
      grid:{vertLines:{visible:false},horzLines:{color:"#223044"}}, rightPriceScale:{borderVisible:false},
      timeScale:{timeVisible:true,borderVisible:false},
      localization:{locale:"pt-BR",timeFormatter:(time:number) => new Date(time*1000).toISOString().replace("T"," ").slice(0,16)+" UTC"} });
    const series = ids.filter(id => runs[id] && visible[id]).map(id => {
      const line = chart.addSeries(LineSeries,{color:colors[id],lineWidth:2,title:strategies[id],priceLineVisible:false});
      line.setData(runs[id]!.simulation.equity.map(p => ({time:p.time as UTCTimestamp,value:Number(p.equity)})));
      return {id,line};
    });
    chart.subscribeCrosshairMove(param => {
      if (typeof param.time !== "number") { setHover(undefined); return; }
      const values: Partial<Record<StrategyId,number>> = {};
      for (const {id,line} of series) { const point=param.seriesData.get(line); if (point && "value" in point) values[id]=point.value; }
      setHover({time:param.time,values});
    });
    chart.timeScale().fitContent();
    return () => { chart.remove(); };
  }, [runs, visible]);
  return <><div className="arena-legend" aria-label="Curvas de patrimônio">{ids.map(id => <button type="button" key={id} aria-pressed={visible[id]}
      onClick={() => setVisible(v => ({...v,[id]:!v[id]}))} className={!visible[id] ? "arena-legend-off" : ""}><i style={{background:colors[id]}}/>{strategies[id]}</button>)}</div>
    <div className="arena-chart" ref={host} role="img" aria-label="Curvas de patrimônio das quatro estratégias em USDT, eixo UTC. Os resultados numéricos estão na tabela."/>
    <div className="arena-chart-readout" aria-live="polite">{hover ? <><span>{new Date(hover.time*1000).toISOString().replace("T"," ").slice(0,16)} UTC</span>{ids.filter(id => hover.values[id] !== undefined).map(id => <span key={id}><i style={{background:colors[id]}}/>{strategies[id]} {number(String(hover.values[id]))} USDT</span>)}</> : "Passe o cursor sobre o gráfico para consultar os valores em UTC."}</div>
    <p className="arena-chart-credit">Patrimônio no fechamento · UTC · <a href="https://www.tradingview.com/lightweight-charts/" target="_blank" rel="noreferrer">Lightweight Charts</a></p></>;
}
