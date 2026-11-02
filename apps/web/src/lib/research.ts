export type Partition = "train" | "validation" | "test";
export const partitions = { train: "Treino", validation: "Validação", test: "Teste fora da amostra" };
export const strategies = { trend: "Trend Following", rsi: "RSI Mean Reversion", breakout: "Breakout", buy_hold: "Buy & Hold" };
export type StrategyId = keyof typeof strategies;
export type Equity = { time: number; equity: string; cash: string; quantity: string; drawdown_pct: string };
export type Fill = { time: number; candle_time: number; side: string; price: string; reference_price: string; quantity: string; fee: string; slippage_cost: string; reason: string; cash_after: string };
export type Trade = { entry: Fill; exit: Fill; pnl: string; return_pct: string; planned_stop: string | null; planned_target: string | null };
export type Metrics = { net_return_pct: string; pnl: string; final_equity: string; max_drawdown_pct: string;
  win_rate_pct: string | null; profit_factor: string | null; expectancy: string | null; closed_trades: number;
  wins: number; losses: number; breakeven: number; realized_win_loss_ratio: string | null; fees: string;
  slippage_cost: string; total_costs: string; exposure_pct: string; undefined: Record<string, string> };
export type Simulation = { metrics: Metrics; equity: Equity[]; trades: Trade[]; fills: Fill[]; rejections: string[];
  plans: { decision_time: number; reason: string; planned_stop: string | null; planned_target: string | null }[];
  portfolio: { cash: string; position: { quantity: string; stop: string | null; target: string | null } | null } };
export type Result = { id: string; manifest: { dataset_hash: string; symbol: string; interval: string; strategy: StrategyId;
  strategy_version: string; start_time: number; end_time: number; protocol_id: string; partition: Partition;
  config: { capital: string; final_policy: string }; code_commit: string; engine_version: string };
  simulation: Simulation; benchmark: Simulation; excess_return_pp: string; warnings: string[] };
export type RunSummary = { id: string; protocol_id: string; partition: Partition; created_at: string };
export type FrozenProtocol = { request: { dataset_hash: string; strategy: StrategyId;
  train_start: number; train_end: number; validation_end: number; test_end: number;
  parameters: { fast: number; slow: number; rsi_period: number; rsi_entry: string; rsi_exit: string; lookback: number;
    stop_fraction: string; target_fraction: string; max_atr_ratio: string | null; volume_multiple: string | null;
    trend_entry: string; trend_exit: string; trend_filter: boolean };
  config: { capital: string; risk_fraction: string; exposure_fraction: string; final_policy: string;
    costs: { fee_rate: string; slippage_rate: string } } } };
export function number(value: string | null, digits = 2) {
  return value === null ? "Indefinido" : Number(value).toLocaleString("pt-BR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
export async function researchFetch<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/research/${path}`, { method: body === undefined ? "GET" : "POST", cache: "no-store",
    headers: { "Content-Type": "application/json", "X-CryptoLab-Research": "1" }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail ?? "Falha na pesquisa local.");
  return data;
}
