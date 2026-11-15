"""Freeze and verify persisted backtests without replay or financial mutation."""
import hashlib
import sqlite3
from pathlib import Path

from cryptolab.config import INTERVALS
from cryptolab.engine.contracts import BacktestResult, ENGINE_VERSION
from cryptolab.history.models import canonical_json
from cryptolab.research.fingerprint import SCHEME
from cryptolab.research.service import LEGACY_COMPATIBLE, ProtocolRequest
from .core import EvidenceError, HEX, MAX_BYTES, strict_json, verify_source


def freeze_backtest(path, run_id):
    if type(run_id) is not str or not HEX.fullmatch(run_id):
        raise EvidenceError("SOURCE_NOT_FOUND")
    try:
        with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            run = db.execute("SELECT id,protocol_id,partition,payload FROM research_runs WHERE id=? AND length(CAST(payload AS BLOB))<=?", (run_id, MAX_BYTES)).fetchone()
            if not run: raise EvidenceError("SOURCE_NOT_FOUND")
            protocol = db.execute("SELECT id,payload FROM research_protocols WHERE id=? AND length(CAST(payload AS BLOB))<=?", (run[1], MAX_BYTES)).fetchone()
            if not protocol: raise EvidenceError("SOURCE_NOT_FOUND")
            parsed = strict_json(protocol[1].encode("utf-8"))
            dataset_id = parsed["request"]["dataset_hash"]
            dataset = db.execute("SELECT id,payload,manifest FROM historical_datasets WHERE id=? AND length(CAST(payload AS BLOB))+length(CAST(manifest AS BLOB))<=?", (dataset_id, MAX_BYTES)).fetchone()
            if not dataset: raise EvidenceError("SOURCE_NOT_FOUND")
            frozen = {"dataset": {"id": dataset[0], "payload": dataset[1], "manifest": dataset[2]},
                      "protocol": {"id": protocol[0], "payload": protocol[1]},
                      "result": {"id": run[0], "protocol_id": run[1], "partition": run[2], "payload": run[3]}}
            verify_backtest(frozen)
            return frozen
    except EvidenceError:
        raise
    except (sqlite3.Error, KeyError, TypeError, AttributeError, UnicodeError):
        raise EvidenceError("SOURCE_UNAVAILABLE") from None


def verify_backtest(frozen):
    try:
        if type(frozen) is not dict or set(frozen) != {"dataset", "protocol", "result"}:
            raise ValueError()
        data = verify_source(frozen["dataset"])
        protocol = frozen["protocol"]
        run = frozen["result"]
        if (type(protocol) is not dict or set(protocol) != {"id", "payload"}
            or type(run) is not dict or set(run) != {"id", "protocol_id", "partition", "payload"}):
            raise ValueError()
        for source in (protocol, run):
            if type(source["id"]) is not str or not HEX.fullmatch(source["id"]) or type(source["payload"]) is not str:
                raise ValueError()
            if hashlib.sha256(source["payload"].encode("utf-8")).hexdigest() != source["id"]:
                raise ValueError()
        p = strict_json(protocol["payload"].encode("utf-8"))
        raw = strict_json(run["payload"].encode("utf-8"))
        metrics = raw["simulation"]["metrics"]
        if any(type(metrics[name]) is not str for name in ("net_return_pct", "max_drawdown_pct", "pnl", "final_equity", "fees", "total_costs")) or type(metrics["closed_trades"]) is not int:
            raise ValueError()
        spec = ProtocolRequest.model_validate(p["request"])
        result = BacktestResult.model_validate(raw)
        m = result.manifest
        scheme = p.get("fingerprint_scheme")
        if scheme == SCHEME:
            dependencies = p["replay_dependencies"]
            if dependencies.get("scheme") != SCHEME or hashlib.sha256(canonical_json(dependencies).encode("utf-8")).hexdigest() != p["code_hash"]:
                raise ValueError()
        elif scheme is not None or p["code_hash"] not in LEGACY_COMPATIBLE:
            raise ValueError()
        bounds = {"train": (spec.train_start, spec.train_end), "validation": (spec.train_end, spec.validation_end), "test": (spec.validation_end, spec.test_end)}
        if (run["protocol_id"] != protocol["id"] or m.protocol_id != protocol["id"] or run["partition"] != m.partition
            or bounds[m.partition] != (m.start_time, m.end_time) or m.dataset_hash != data.reference_hash
            or spec.dataset_hash != data.reference_hash or m.symbol != data.manifest["symbol"]
            or m.interval != data.manifest["interval"] or m.warmup_start != data.start_time
            or spec.train_start < data.start_time or spec.test_end > data.end_time
            or m.strategy != spec.strategy or m.parameters != spec.parameters or m.config != spec.config
            or m.instrument.model_dump(mode="json") != p["instrument"]
            or m.engine_version != p["engine_version"] or m.engine_version != ENGINE_VERSION or m.code_hash != p["code_hash"] or m.code_commit != p["code_commit"]
            or any(t % INTERVALS[m.interval] for t in (spec.train_start, spec.train_end, spec.validation_end, spec.test_end))
            or m.strategy_version != "1"):
            raise ValueError()
        # Hash verification authenticates the frozen representation, not provenance
        # or recomputation. Do not import or execute the strategy.
        return data, result
    except (KeyError, ValueError, TypeError, AttributeError, UnicodeError):
        raise EvidenceError("BACKTEST_SOURCE_UNVERIFIED") from None
