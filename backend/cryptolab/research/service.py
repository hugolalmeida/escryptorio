import hashlib
import json
import subprocess
from decimal import localcontext
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from cryptolab.config import INTERVALS
from cryptolab.engine.backtest import simulate
from cryptolab.engine.contracts import (BacktestConfig, BacktestResult, Contract, InstrumentRules,
    RunManifest, StrategyId, StrategyParameters, ENGINE_VERSION)
from cryptolab.engine.strategies import warmup
from cryptolab.history.models import canonical_json
from cryptolab.history.reader import DatasetReader
from cryptolab.history.storage import HistoryStore
from cryptolab.research.fingerprint import SCHEME, legacy_fingerprint, replay_fingerprint

MAX_RESEARCH_CANDLES = 20_000


def digest(value) -> tuple[str, str]:
    payload = canonical_json(value)
    return hashlib.sha256(payload.encode()).hexdigest(), payload


def code_reference() -> dict:
    package = Path(__file__).resolve().parents[1]
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=package, capture_output=True,
                                text=True, check=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = "unavailable"
    return {"code_commit": commit, "engine_version": ENGINE_VERSION, **replay_fingerprint()}


class ProtocolRequest(Contract):
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    strategy: StrategyId
    parameters: StrategyParameters = StrategyParameters()
    config: BacktestConfig = BacktestConfig()
    train_start: int = Field(ge=0)
    train_end: int = Field(ge=0)
    validation_end: int = Field(ge=0)
    test_end: int = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self):
        if not self.train_start < self.train_end < self.validation_end < self.test_end:
            raise ValueError("Treino, validação e teste devem ser cronológicos e não sobrepostos")
        return self


class RunRequest(Contract):
    protocol_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    partition: Literal["train", "validation", "test"]


class ResearchError(ValueError):
    pass


class ResearchService:
    def __init__(self, store: HistoryStore):
        self.store = store

    def instrument(self, symbol: str, interval: str) -> InstrumentRules:
        snapshot = self.store.load(symbol, interval)
        if snapshot is None:
            raise ResearchError("INSTRUMENT_UNAVAILABLE: colete um snapshot público antes de criar o protocolo")
        raw = snapshot.instrument
        try:
            lot = raw["lot_size_filter"]
            if raw["symbol"] != symbol or raw["status"] != "Trading" or raw["quote_coin"] != "USDT":
                raise ValueError()
            return InstrumentRules(symbol=symbol, quantity_step=lot["basePrecision"],
                price_tick=raw["price_filter"]["tickSize"], min_quantity="0",
                min_notional=lot["minOrderAmt"], max_quantity=lot["maxMarketOrderQty"],
                source_time_ms=raw["source_time_ms"], source_hash=digest(raw)[0])
        except (KeyError, ValueError, TypeError):
            raise ResearchError("INSTRUMENT_INVALID: limites públicos ausentes ou inválidos") from None

    def freeze(self, request: ProtocolRequest) -> dict:
        reference = code_reference()
        if reference["code_hash"] != STARTUP_CODE_HASH:
            raise ResearchError("ENGINE_CHANGED_RESTART_REQUIRED: reinicie o processo de pesquisa")
        data = DatasetReader(self.store).read(request.dataset_hash)
        step = INTERVALS[data.manifest["interval"]]
        boundaries = (request.train_start, request.train_end, request.validation_end, request.test_end)
        if (any(t % step for t in boundaries) or request.train_start < data.start_time
                or request.test_end > data.end_time or any(b-a < 2*step for a, b in zip(boundaries, boundaries[1:]))
                or (request.test_end-data.start_time)//step > MAX_RESEARCH_CANDLES):
            raise ResearchError("INVALID_RESEARCH_RANGE: limites alinhados, dois candles por janela e até 20.000 candles com warm-up")
        if (request.train_start-data.start_time)//step+1 < warmup(request.strategy, request.parameters):
            raise ResearchError("INSUFFICIENT_WARMUP: reserve histórico anterior ao treino")
        protocol = {"request": request.model_dump(mode="json"),
                    "instrument": self.instrument(data.manifest["symbol"], data.manifest["interval"]).model_dump(mode="json"),
                    **reference}
        identifier, payload = digest(protocol)
        with self.store.connect() as db:
            db.execute("INSERT OR IGNORE INTO research_protocols(id,payload) VALUES (?,?)", (identifier, payload))
        return {"id": identifier, **protocol}

    def protocol(self, identifier: str) -> dict:
        with self.store.connect() as db:
            row = db.execute("SELECT payload FROM research_protocols WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ResearchError("PROTOCOL_NOT_FOUND")
        if hashlib.sha256(row[0].encode()).hexdigest() != identifier:
            raise ResearchError("PROTOCOL_HASH_MISMATCH")
        return json.loads(row[0])

    def run(self, request: RunRequest) -> dict:
        protocol = self.protocol(request.protocol_id)
        spec = ProtocolRequest.model_validate(protocol["request"])
        current = code_reference()
        if current["code_hash"] != STARTUP_CODE_HASH:
            raise ResearchError("ENGINE_CHANGED_RESTART_REQUIRED: reinicie o processo de pesquisa")
        scheme = protocol.get("fingerprint_scheme")
        if scheme is None:
            # Legacy protocols retain the original all-backend fingerprint semantics.
            compatible = legacy_fingerprint() == protocol["code_hash"] or LEGACY_COMPATIBLE.get(protocol["code_hash"]) == current["code_hash"]
        elif scheme == SCHEME:
            compatible = protocol["code_hash"] == current["code_hash"] and protocol.get("replay_dependencies") == current["replay_dependencies"]
        else:
            raise ResearchError("UNKNOWN_FINGERPRINT_SCHEME: revisão do protocolo necessária")
        if not compatible or current["engine_version"] != protocol["engine_version"]:
            raise ResearchError("ENGINE_CHANGED: use o código original ou crie um novo protocolo")
        if request.partition == "test":
            with self.store.connect() as db:
                seen = {r[0] for r in db.execute("SELECT partition FROM research_runs WHERE protocol_id=?", (request.protocol_id,))}
            if not {"train", "validation"} <= seen:
                raise ResearchError("TEST_REQUIRES_TRAIN_VALIDATION: execute treino e validação do protocolo congelado")
        start, end = {"train": (spec.train_start, spec.train_end),
            "validation": (spec.train_end, spec.validation_end), "test": (spec.validation_end, spec.test_end)}[request.partition]
        data = DatasetReader(self.store).read(spec.dataset_hash)
        rules = InstrumentRules.model_validate(protocol["instrument"])
        step = INTERVALS[data.manifest["interval"]]
        manifest = RunManifest(dataset_hash=spec.dataset_hash, symbol=data.manifest["symbol"], interval=data.manifest["interval"],
            start_time=start, end_time=end, warmup_start=data.start_time, strategy=spec.strategy,
            parameters=spec.parameters, config=spec.config, instrument=rules, protocol_id=request.protocol_id,
            partition=request.partition, code_commit=protocol["code_commit"], code_hash=protocol["code_hash"])
        simulation = simulate(data.candles, step, start, end, spec.strategy, spec.parameters, spec.config, rules)
        benchmark = simulation if spec.strategy == "buy_hold" else simulate(data.candles, step, start, end,
            "buy_hold", spec.parameters, spec.config, rules)
        warnings = ["Pesquisa histórica simulada; desempenho passado não estima retorno futuro.",
            "Sem liquidez, fills parciais ou caminho intrabar; stops não garantem perda máxima.",
            "Regras do instrumento são snapshot público, não regras históricas verificadas."]
        if simulation.metrics.closed_trades < 30:
            warnings.append("Amostra insuficiente: menos de 30 trades encerrados; nenhum vencedor validado.")
        if simulation.portfolio.position:
            warnings.append("Posição aberta marcada a mercado; custos de saída ainda não realizados.")
        with localcontext() as ctx:
            ctx.prec = 34
            result = BacktestResult(manifest=manifest, simulation=simulation, benchmark=benchmark,
                excess_return_pp=simulation.metrics.net_return_pct-benchmark.metrics.net_return_pct, warnings=tuple(warnings))
        identifier, payload = digest(result.model_dump(mode="json"))
        with self.store.connect() as db:
            db.execute("INSERT OR IGNORE INTO research_runs(id,protocol_id,partition,payload) VALUES (?,?,?,?)",
                       (identifier, request.protocol_id, request.partition, payload))
        return {"id": identifier, **json.loads(payload)}

    def result(self, identifier: str) -> dict:
        with self.store.connect() as db:
            row = db.execute("SELECT payload FROM research_runs WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ResearchError("RUN_NOT_FOUND")
        if hashlib.sha256(row[0].encode()).hexdigest() != identifier:
            raise ResearchError("RUN_HASH_MISMATCH")
        return {"id": identifier, **json.loads(row[0])}

    def runs(self) -> list[dict]:
        with self.store.connect() as db:
            rows = db.execute("SELECT id,protocol_id,partition,created_at FROM research_runs ORDER BY created_at DESC,id DESC LIMIT 50").fetchall()
        return [dict(r) for r in rows]

    def verify(self, identifier: str) -> dict:
        result = self.result(identifier)
        replay = self.run(RunRequest(protocol_id=result["manifest"]["protocol_id"], partition=result["manifest"]["partition"]))
        return {"id": identifier, "replayed_id": replay["id"], "identical": identifier == replay["id"]}


# Explicit, audited compatibility bridges only. Never infer compatibility from an old commit alone.
LEGACY_COMPATIBLE = {
    # Phase 2.2 legacy tree and exact scoped/runtime fingerprint audited against
    # persisted real runs. This does not authorize any other legacy tree.
    "85a5b51ab9a8a9a77e6e32f3ec887103b5dce701015077bf00b0335095d2168d":
        "e3adfd0e20b3cdcad31a596ae3287aabeebcb65abc458f7541f23f063ecc3f62",
}
STARTUP_CODE_HASH = replay_fingerprint()["code_hash"]
