import type { Candle, Interval, SymbolName } from "@/lib/market";

export type Span = { start_time: number; end_time: number; candle_count: number };
export type Coverage = { source: string; market: string; symbol: SymbolName; interval: Interval;
  start_time: number; end_time: number; stored_count: number; expected_count: number;
  coverage_ratio: number; complete: boolean; segments: Span[]; gaps: Span[] };
export type HistoryJob = { id: string; symbol: SymbolName; interval: Interval; start_time: number; end_time: number;
  status: "queued" | "running" | "paused" | "failed" | "incomplete" | "completed";
  stored_count: number; expected_count: number; pages: number; cancel_requested: number;
  error_code: string | null; dataset_id: string | null; updated_at_ms: number;
  runs: { id: number; status: string; error_code: string | null }[]; gaps: Span[] };
export type DatasetManifest = { dataset_id: string; sha256: string; schema_version: number; source: string; market: string;
  symbol: SymbolName; interval: Interval; start_time: number; end_time: number; candle_count: number;
  gaps: Span[]; coverage_ratio: number; integrity_status: string; approved_at_ms: number;
  first_collected_at_ms: number; last_collected_at_ms: number; collector_version: string; pybit_version: string };
export type DatasetPreview = { reference_hash: string; manifest: DatasetManifest; candles: Candle[]; total_count: number };

export const jobLabels: Record<HistoryJob["status"], string> = { queued: "Na fila", running: "Coletando", paused: "Pausada",
  failed: "Falhou", incomplete: "Incompleta", completed: "Concluída" };
export function utcTime(seconds: number) {
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "UTC" }).format(seconds * 1000);
}
export function timeframe(interval: Interval) { return interval === "D" ? "1d" : interval === "60" ? "1h" : interval === "240" ? "4h" : "15m"; }
export function count(value: number) { return value.toLocaleString("pt-BR"); }
export async function historyFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/history/${path}`, { cache: "no-store", ...options,
    headers: { "Content-Type": "application/json", "X-CryptoLab-Research": "1", ...options?.headers } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail ?? "Falha na pesquisa histórica.");
  return data;
}
