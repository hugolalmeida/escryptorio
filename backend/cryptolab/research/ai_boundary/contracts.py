"""Closed, immutable contracts for the trusted research boundary."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..evidence.core import EvidenceError, canonical, digest, strict_json

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(min_length=1, max_length=256)]
Count = Annotated[int, Field(ge=0, le=2**53 - 1)]
CONTEXT_LIMIT = 32768


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Window(Closed):
    start_ms: Count
    end_ms: Count

    @model_validator(mode="after")
    def ordered(self):
        if self.start_ms >= self.end_ms:
            raise ValueError("WINDOW_INVALID")
        return self


class Observation(Closed):
    claim_id: Hash
    validation_id: Hash
    name: Literal["dataset_id", "symbol", "interval", "window", "candle_count",
                  "net_return_pct", "max_drawdown_pct", "pnl", "final_equity",
                  "fees", "total_costs", "closed_trades"]
    value: Text | Count | Window
    unit: Literal["sha256", "symbol", "interval", "utc_ms", "count", "percent", "USDT"]
    method: Literal["dataset-reader/1", "persisted-backtest/1"]
    source_ref: Hash
    window: Window
    status: Literal["VALIDATED"]
    point_in_time: Literal["UNVERIFIED_POINT_IN_TIME"]
    limitations: Annotated[tuple[Text, ...], Field(max_length=8)]


class Context(Closed):
    schema_version: Literal[1]
    builder_version: Literal["research-context/1"]
    policy_version: Literal["minimal-v2/1"]
    context_id: Hash
    content_hash: Hash
    evidence_content_hash: Hash
    research_objective: Literal["DESCRIBE_VERIFIED_CONTEXT"]
    mode: Literal["RETROSPECTIVE"]
    symbol: Literal["BTCUSDT", "ETHUSDT"]
    interval: Literal["15", "60", "240", "D"]
    as_of_ms: Count
    window: Window
    source_refs: Annotated[tuple[Hash, ...], Field(min_length=3, max_length=3)]
    observations: Annotated[tuple[Observation, ...], Field(max_length=100)]
    rejected_claims: Annotated[int, Field(ge=0, le=100)]
    point_in_time: Literal["UNVERIFIED_POINT_IN_TIME"]
    analysis_scope: Literal["RETROSPECTIVE_ANALYSIS"]
    limitations: Annotated[tuple[Text, ...], Field(max_length=8)]
    uncertainty: Annotated[tuple[Text, ...], Field(max_length=8)]
    missing_evidence: Annotated[tuple[Text, ...], Field(max_length=8)]


def parse_context(raw):
    if type(raw) is not bytes or len(raw) > CONTEXT_LIMIT:
        raise EvidenceError("CONTEXT_SIZE_LIMIT")
    try:
        value = strict_json(raw)
        if type(value) is not dict or type(value.get("schema_version")) is not int:
            raise ValueError()
        context = Context.model_validate_json(canonical(value))
        body = context.model_dump(mode="json", exclude={"content_hash", "context_id"})
        expected = digest("escryptorio:research-context:v1", body)
        if context.content_hash != expected or context.context_id != expected:
            raise ValueError()
        if context.window.end_ms > context.as_of_ms:
            raise ValueError()
        return context
    except (ValueError, TypeError):
        raise EvidenceError("CONTEXT_INVALID") from None
