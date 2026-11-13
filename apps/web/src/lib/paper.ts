export type Wallet = {
  wallet_id: string; wallet_hash: string; head_hash: string; sequence: number; ledger_version: string;
  spec: { bot_id: string; strategy: string; symbol: string; interval: string; initial_capital: string };
  state: { cash: string; quantity: string; acquisition_cost: string; realized_pnl: string; total_fees: string; state: string };
  mark_status: string; mark_price: string | null; mark_source_time_ms: number | null; mark_id: string | null;
  average_cost: string | null; position_value: string | null; exposure: string | null; equity: string | null;
  unrealized_pnl: string | null; total_pnl: string | null; last_event_time: number;
  binding?: { id: string; state: string; planner_version: string; binding: { risk: unknown } } | null;
};
export type Overview = { summary: { initial_capital: string; cash: string; equity: string | null; position_value: string | null; realized_pnl: string; unrealized_pnl: string | null; total_pnl: string | null; wallets: number; positions: number; fills: number; decisions: number; integrity: string }; wallets: Wallet[]; markets: { symbol: string; status: string; source_time_ms: number | null }[]; collection: { last_success_ms: number | null; error_code: string | null } | null; monitor_status: string };
export type Signal = { id: string; definition: { config: { bot_id: string; strategy: string; symbol: string; interval: string }; monitor_hash?: string }; config_hash: string; dataset_id: string; candle_time: number; decision_time: number; valid_until: number; origin?: string; temporal_status: string; if_flat: { action: string }; if_long: { action: string } };
export type Decision = { id: string; wallet_id: string; binding_id: string; signal_id: string; action: string; state: string; temporal_status: string; reason: string; execution_id: string | null };
export type Event = { sequence: number; event_id: string; kind: string; payload: { input: null | { side?: string; quantity?: string; price?: string; reference_price?: string; fee?: string; event_time?: number }; after: { equity: string | null } } };
export type Fill = { event: Event; provenance: string; execution_id: string | null; decision_id: string | null; slippage: string | null };
export type Page<T> = { items: T[]; total: number; offset: number; limit: number };
export type Point = { time: number; value: string; kind: string; sequence: number };
export type Envelope<T> = { schema_version: number; observed_at_ms: number; data: T };
export async function paperGet<T>(path: string, signal: AbortSignal): Promise<Envelope<T>> {
  const response = await fetch(`/api/paper/${path}`, { cache: "no-store", signal });
  if (!response.ok) throw new Error("Dados paper indisponíveis ou falha de integridade.");
  const body = await response.json() as Envelope<T>;
  if (body.schema_version !== 1 || !body.data) throw new Error("Resposta paper inválida.");
  const data = body.data as Record<string, unknown>;
  if (path === "overview" && (!Array.isArray(data.wallets) || !Array.isArray(data.markets) || !data.summary || typeof data.summary !== "object")) throw new Error("Resposta paper inválida.");
  if ((path === "signals" || path === "decisions") && !Array.isArray(body.data)) throw new Error("Resposta paper inválida.");
  if ((path.includes("/fills?") || path.includes("/events?") || path.endsWith("/equity")) && !Array.isArray(data.items)) throw new Error("Resposta paper inválida.");
  return body;
}
export const money = (value: string | null | undefined) => value == null ? "Indisponível" : `${value} USDT`;
export const date = (seconds: number | null | undefined) => seconds == null ? "Indisponível" : new Date(seconds * 1000).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });
