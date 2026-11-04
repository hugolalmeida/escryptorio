import type { Partition, Result, StrategyId } from "@/lib/research";

export const ids: StrategyId[] = ["trend", "rsi", "breakout", "buy_hold"];
export const colors: Record<StrategyId, string> = { trend: "#8bb9fb", rsi: "#69d3b4", breakout: "#d5b679", buy_hold: "#b39be8" };
export type Parameters = { fast: number; slow: number; trend_entry: string; trend_exit: string; max_atr_ratio: string | null;
  rsi_period: number; rsi_entry: string; rsi_exit: string; trend_filter: boolean; lookback: number; volume_multiple: string | null;
  stop_fraction: string; target_fraction: string };
export type ArenaConfig = { dataset_hash: string; symbol: string; interval: string; train_start: number; train_end: number;
  validation_end: number; test_end: number; backtest: { capital: string; risk_fraction: string; exposure_fraction: string;
    final_policy: string; costs: { fee_rate: string; slippage_rate: string } };
  strategies: Record<StrategyId, { version: string; parameters: Parameters }>; protocol_ids: Record<StrategyId,string> | null };
export type Experiment = { id: string; arena_version: string; config: ArenaConfig; protocol_ids: Record<StrategyId,string> };
export type ExperimentSummary = { id: string; created_at: string };
export type Entry = { rank: number; strategy: StrategyId; strategy_version: string; parameters: Parameters; protocol_id: string; run_id: string;
  net_return_pct: string; max_drawdown_pct: string; profit_factor: string | null; win_rate_pct: string | null; closed_trades: number;
  expectancy: string | null; total_costs: string; exposure_pct: string; excess_return_pp: string; undefined: Record<string,string>; insufficient_sample: boolean };
export type ArenaResult = { id: string; experiment_id: string; arena_version: string; run_ids: Record<Partition,Record<StrategyId,string>>;
  rankings: Record<Partition,{ start_time: number; end_time: number; out_of_sample: boolean; entries: Entry[];
    insufficient_sample: boolean; validated_winner: null }>; warnings: string[] };
export type Runs = Partial<Record<StrategyId, Result>>;
export class ArenaRequestError extends Error { constructor(message: string, public status: number) { super(message); } }
export async function arenaFetch<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/arena/${path}`, { method: body === undefined ? "GET" : "POST", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-CryptoLab-Research": "1" }, body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(body !== undefined && path === "execute" ? 125000 : 25000) });
  } catch (error) {
    throw new ArenaRequestError(error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError") ? "Tempo excedido." : "Backend local indisponível.", 0);
  }
  let data: { detail?: unknown } & Record<string, unknown>;
  try {
    data = await response.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Invalid response");
  }
  catch { throw new ArenaRequestError("Resposta inválida do serviço local.", response.status >= 500 ? response.status : 503); }
  if (!response.ok) throw new ArenaRequestError(typeof data.detail === "string" ? data.detail : "Falha na Arena.", response.status);
  return data as T;
}
