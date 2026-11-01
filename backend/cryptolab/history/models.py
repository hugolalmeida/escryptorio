import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from cryptolab.config import INTERVALS
from cryptolab.models import Candle, Interval, Symbol

COLLECTOR_VERSION = "bybit-v5-history/1"
MAX_CANDLES = 100_000


def utc_iso(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> int:
    """Datas simples são meia-noite UTC. ISO com hora exige offset explícito."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if len(value) == 10:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None or parsed.microsecond:
        raise ValueError("Use data UTC ou ISO 8601 com offset, sem frações de segundo")
    return int(parsed.timestamp())


class HistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    symbol: Symbol
    interval: Interval
    start: str
    end: str

    @model_validator(mode="after")
    def validate_range(self):
        start, end, step = self.start_time, self.end_time, INTERVALS[self.interval]
        if start < 0 or end <= start or start % step or end % step:
            raise ValueError("Período [início, fim) deve ser positivo e alinhado ao timeframe em UTC")
        if (end - start) // step > MAX_CANDLES:
            raise ValueError(f"Limite de {MAX_CANDLES} candles por solicitação; divida o período")
        return self

    @property
    def start_time(self) -> int:
        return parse_utc(self.start)

    @property
    def end_time(self) -> int:
        return parse_utc(self.end)

    @property
    def expected_count(self) -> int:
        return (self.end_time - self.start_time) // INTERVALS[self.interval]


def decimal_text(value: Decimal) -> str:
    # Não usa normalize(): normalize depende do contexto Decimal global e pode arredondar.
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def candle_record(candle: Candle) -> dict:
    return {"time": candle.time, **{name: decimal_text(getattr(candle, name))
            for name in ("open", "high", "low", "close", "volume", "turnover")}}


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def candle_payload(candle: Candle) -> str:
    if not candle.closed:
        raise ValueError("Candle aberto não pode ser persistido no histórico")
    # Revalidar mesmo se o objeto tiver sido construído via model_copy/model_construct.
    checked = Candle.model_validate(candle.model_dump())
    return canonical_json(candle_record(checked))


def missing_ranges(times: list[int], start: int, end: int, step: int) -> list[dict]:
    result = []
    cursor = start
    for stamp in times:
        if stamp < start or stamp >= end:
            continue
        if stamp < cursor or stamp % step:
            raise ValueError("Histórico fora de ordem, duplicado ou desalinhado")
        if stamp > cursor:
            result.append({"start_time": cursor, "end_time": stamp, "candle_count": (stamp-cursor)//step})
        cursor = stamp + step
    if cursor < end:
        result.append({"start_time": cursor, "end_time": end, "candle_count": (end-cursor)//step})
    return result


def canonical_history(request: HistoryRequest, candles: list[Candle]) -> tuple[str, str]:
    step = INTERVALS[request.interval]
    if len(candles) != request.expected_count or any(c.time != request.start_time + i*step
            for i, c in enumerate(candles)):
        raise ValueError("Aprovação exige cobertura completa e cronológica")
    rows = [json.loads(candle_payload(c)) for c in candles]
    payload = canonical_json({"schema_version": 1, "source": "Bybit", "market": "spot",
        "symbol": request.symbol, "interval": request.interval, "start_time": request.start_time,
        "end_time": request.end_time, "candles": rows})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), payload
