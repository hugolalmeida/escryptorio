"""Contratos de simulação local; não contêm cliente ou ordem de corretora."""
from typing import Literal
from pydantic import Field, model_validator
from cryptolab.paper.models import PaperContract
from cryptolab.paper.planner_models import reject_float
from cryptolab.models import Symbol, Interval


class StrictPaperContract(PaperContract):
    @model_validator(mode="before")
    @classmethod
    def no_nested_floats(cls, value):
        reject_float(value)
        return value


class VirtualExecutionRequest(StrictPaperContract):
    schema_version: Literal[1] = 1
    decision_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}$")


class ExecutionCheckpoint(StrictPaperContract):
    wallet_sequence: int = Field(ge=1)
    wallet_head_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class PaperMarkProvenance(StrictPaperContract):
    schema_version: Literal[1] = 1
    executor_version: str
    wallet_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    binding_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    signal_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}$")
    symbol: Symbol
    interval: Interval
    snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    instrument_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    ticker_source_time_ms: int = Field(ge=0)
    market_source_time_ms: int = Field(ge=0)
    fetched_at_ms: int = Field(ge=0)
    marked_at_ms: int = Field(ge=0)
    max_age_seconds: int = Field(ge=1, le=300)
    candle_time: int = Field(ge=0)
    price: str
    event_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    event_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    snapshot: dict


class VirtualFillEvidence(StrictPaperContract):
    schema_version: Literal[1] = 1
    executor_version: str
    decision_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    wallet_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    binding_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    signal_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}$")
    symbol: Symbol
    interval: Interval
    action: Literal["BUY", "SELL"]
    candle_time: int = Field(ge=0)
    fill_candle_time: int = Field(ge=0)
    execution_time_ms: int = Field(ge=0)
    ticker_source_time_ms: int = Field(ge=0)
    fetched_at_ms: int = Field(ge=0)
    max_age_seconds: int = Field(ge=1, le=300)
    snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    instrument_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    mark_id: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    decision_event_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    binding_event_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    event_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    event_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    before: ExecutionCheckpoint
    after: ExecutionCheckpoint
    proposal: dict
    snapshot: dict
    protection: dict | None


class VirtualExecutionResult(StrictPaperContract):
    schema_version: Literal[1] = 1
    status: Literal["CONSUMED"] = "CONSUMED"
    execution_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    receipt_mode: Literal["NEW_VIRTUAL_FILL", "RECOVER_VIRTUAL_FILL"]
    evidence: dict
    ledger_event: dict
    live_execution_enabled: Literal[False] = False
