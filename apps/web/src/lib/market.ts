export const SYMBOLS = ["BTCUSDT", "ETHUSDT"] as const;
export type SymbolName = typeof SYMBOLS[number];
export const INTERVALS = [{ value: "15", label: "15m" }, { value: "60", label: "1h" },
  { value: "240", label: "4h" }, { value: "D", label: "1d" }] as const;
export type Interval = typeof INTERVALS[number]["value"];
export type Candle = { time: number; open: string; high: string; low: string; close: string;
  volume: string; turnover: string; closed: boolean };
export type Point = { time: number; value: string };
export type Market = {
  symbol: SymbolName; interval: Interval; category: "spot"; source: "Bybit";
  source_time_ms: number; fetched_at_ms: number; served_at_ms: number;
  stale: boolean; stale_after_seconds: number; dataset_id: string;
  ticker: { price: string; change_24h: string; high_24h: string; low_24h: string;
    volume_24h: string; turnover_24h: string; source_time_ms: number };
  candles: Candle[];
  indicators: { sma_20: Point[]; ema_50: Point[]; rsi_14: string | null; atr_14: string | null;
    trend: "alta" | "baixa" | "neutra" | "insuficiente"; closed_candles: number; as_of: number | null };
  instrument: { price_filter: Record<string, string>; lot_size_filter: Record<string, string>; source_time_ms: number };
};

export function price(value: string | number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value));
}
export function compact(value: string | null | undefined) {
  return value == null ? "—" : new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 2 }).format(Number(value));
}
export function clock(ms: number | undefined) {
  return ms == null ? "—" : new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit",
    timeZone: "America/Sao_Paulo" }).format(ms);
}
export function datetime(ms: number) {
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium", timeZone: "America/Sao_Paulo" }).format(ms);
}
