"""Pure, immutable research contracts. No I/O or exchange client."""
from decimal import Decimal as D
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cryptolab.models import Symbol, Interval

ENGINE_VERSION = "cryptolab-replay/1"
StrategyId = Literal["trend", "rsi", "breakout", "buy_hold"]


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False, validate_default=True)


class StrategyParameters(Contract):
    fast: int = Field(20, ge=2, le=500)
    slow: int = Field(50, ge=3, le=500)
    trend_entry: Literal["cross", "state"] = "cross"
    trend_exit: Literal["averages", "close_fast"] = "averages"
    max_atr_ratio: D | None = Field(None, gt=0, le=1)
    rsi_period: int = Field(14, ge=2, le=500)
    rsi_entry: D = Field(D(30), gt=0, lt=100)
    rsi_exit: D = Field(D(60), gt=0, lt=100)
    trend_filter: bool = False
    lookback: int = Field(20, ge=2, le=500)
    volume_multiple: D | None = Field(None, gt=0, le=100)
    stop_fraction: D = Field(D("0.03"), gt=0, lt=1)
    target_fraction: D = Field(D("0.06"), gt=0, le=10)

    @model_validator(mode="after")
    def ordered(self):
        if self.fast >= self.slow or self.rsi_entry >= self.rsi_exit:
            raise ValueError("Médias e limiares devem estar em ordem crescente")
        return self


class CostModel(Contract):
    fee_rate: D = Field(D("0.001"), ge=0, le=D("0.05"))
    slippage_rate: D = Field(D("0.0005"), ge=0, le=D("0.05"))


class InstrumentRules(Contract):
    symbol: Symbol
    quantity_step: D = Field(gt=0)
    price_tick: D = Field(gt=0)
    min_quantity: D = Field(ge=0)
    min_notional: D = Field(gt=0)
    max_quantity: D = Field(gt=0)
    max_notional: D | None = Field(None, gt=0)
    source_time_ms: int = Field(ge=0)
    source_hash: str
    assumption: str = "Snapshot público local; regras históricas não verificadas"

    @model_validator(mode="after")
    def limits(self):
        if self.min_quantity > self.max_quantity or (self.max_notional is not None and self.min_notional > self.max_notional):
            raise ValueError("Limites de instrumento inconsistentes")
        return self


class BacktestConfig(Contract):
    capital: D = Field(D(10000), gt=0, le=D("1000000000"))
    risk_fraction: D = Field(D("0.01"), gt=0, le=1)
    exposure_fraction: D = Field(D(1), gt=0, le=1)
    costs: CostModel = CostModel()
    final_policy: Literal["liquidate", "mark_to_market"] = "liquidate"


class SignalPlan(Contract):
    decision_time: int
    valid_at_open: int
    reference_price: D
    planned_stop: D | None
    planned_target: D | None
    reward_risk: D | None
    reason: str
    invalidation: str = "Válido apenas na próxima abertura; cancelar se não houver saldo ou limites válidos"


class Decision(Contract):
    action: Literal["buy", "sell", "hold"]
    reason: str


class OrderIntent(Contract):
    side: Literal["buy", "sell"]
    plan: SignalPlan


class Fill(Contract):
    side: Literal["buy", "sell"]
    time: int
    candle_time: int
    decision_time: int | None
    price: D
    reference_price: D
    quantity: D
    fee: D
    slippage_cost: D
    reason: str
    cash_after: D


class Position(Contract):
    quantity: D
    entry: Fill
    stop: D | None
    target: D | None


class Portfolio(Contract):
    cash: D
    position: Position | None = None


class Trade(Contract):
    entry: Fill
    exit: Fill
    pnl: D
    return_pct: D
    planned_stop: D | None
    planned_target: D | None


class EquityPoint(Contract):
    time: int
    equity: D
    cash: D
    quantity: D
    drawdown_pct: D


class BacktestMetrics(Contract):
    net_return_pct: D
    pnl: D
    final_equity: D
    max_drawdown_pct: D
    win_rate_pct: D | None
    profit_factor: D | None
    expectancy: D | None
    closed_trades: int
    wins: int
    losses: int
    breakeven: int
    realized_win_loss_ratio: D | None
    fees: D
    slippage_cost: D
    total_costs: D
    exposure_pct: D
    undefined: dict[str, str]


class RunManifest(Contract):
    dataset_hash: str
    symbol: Symbol
    interval: Interval
    start_time: int
    end_time: int
    warmup_start: int
    strategy: StrategyId
    strategy_version: str = "1"
    parameters: StrategyParameters
    engine_version: str = ENGINE_VERSION
    code_commit: str
    code_hash: str
    protocol_id: str
    partition: Literal["train", "validation", "test"]
    config: BacktestConfig
    instrument: InstrumentRules
    execution_rules: str = "next_open;stop_first;gap_at_open;adverse_tick_rounding;fees_quote;decimal34;one_long;v1"


class Simulation(Contract):
    metrics: BacktestMetrics
    equity: tuple[EquityPoint, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    plans: tuple[SignalPlan, ...]
    rejections: tuple[str, ...]
    portfolio: Portfolio


class BacktestResult(Contract):
    manifest: RunManifest
    simulation: Simulation
    benchmark: Simulation
    excess_return_pp: D
    warnings: tuple[str, ...]


class Strategy(Protocol):
    identifier: StrategyId
    version: str

    def decide(self, index: int, in_position: bool) -> Decision: ...
