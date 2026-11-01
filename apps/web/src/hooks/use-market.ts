"use client";

import { useCallback, useEffect, useState } from "react";
import { SYMBOLS, type Interval, type Market } from "@/lib/market";

type Entry = { data?: Market; error?: string; loading: boolean };
export function useMarket(interval: Interval) {
  const [entries, setEntries] = useState<Record<string, Entry>>({});
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(0);
  const reload = useCallback(() => setRefresh(n => n + 1), []);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;
    const fetchAll = async () => {
      if (inFlight) return;
      inFlight = true;
      await Promise.allSettled(SYMBOLS.map(async symbol => {
        const key = `${symbol}:${interval}`;
        setEntries(prev => ({ ...prev, [key]: { ...prev[key], loading: true } }));
        try {
          const response = await fetch(`/api/market?symbol=${symbol}&interval=${interval}`, {
            cache: "no-store", signal: controller.signal,
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail ?? "Falha na atualização do mercado.");
          if (!controller.signal.aborted) setEntries(prev => ({ ...prev, [key]: { data, loading: false } }));
        } catch (error) {
          if (!controller.signal.aborted) setEntries(prev => ({ ...prev, [key]: { ...prev[key], loading: false,
            error: error instanceof Error ? error.message : "Falha na atualização." } }));
        }
      }));
      inFlight = false;
    };
    void fetchAll();
    const timer = setInterval(() => void fetchAll(), 15000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [interval, refresh]);
  return { entries, reload, now };
}
