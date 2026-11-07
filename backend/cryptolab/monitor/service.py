"""Avaliação offline de snapshots públicos; não importa paper, SDK ou execução."""
import hashlib
import json
import time
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

from cryptolab.config import INTERVALS
from cryptolab.engine.strategies import ResearchStrategy, warmup
from cryptolab.history.models import canonical_json, decimal_text
from cryptolab.models import Snapshot
from cryptolab.monitor.models import MonitorConfig
from cryptolab.research.fingerprint import replay_fingerprint
from cryptolab.storage import Store, canonical_dataset

MONITOR_VERSION = "cryptolab-monitor/1"
STARTUP_ENGINE_HASH = replay_fingerprint()["code_hash"]


class MonitorError(ValueError):
    pass


def digest(value):
    payload = canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), payload


def validated(snapshot: Snapshot, config: MonitorConfig, now_ms: int, max_age: int):
    step = INTERVALS[config.interval]
    if snapshot.symbol != config.symbol or snapshot.interval != config.interval or snapshot.source != "Bybit" or snapshot.category != "spot":
        raise MonitorError("MARKET_MISMATCH")
    for stamp in (snapshot.source_time_ms, snapshot.fetched_at_ms):
        if stamp > now_ms+5000 or now_ms-stamp > max_age*1000:
            raise MonitorError("STALE_SNAPSHOT")
    candles = tuple(snapshot.candles)
    if (not candles or any(c.time % step for c in candles)
        or any(b.time-a.time != step for a,b in zip(candles,candles[1:]))
        or any(not a.closed and b.closed for a,b in zip(candles,candles[1:]))):
        raise MonitorError("INVALID_CANDLE_SEQUENCE")
    source_seconds = snapshot.source_time_ms//1000
    if any(c.time > source_seconds or c.closed != (c.time+step <= source_seconds) for c in candles):
        raise MonitorError("INVALID_CANDLE_CLOSURE")
    closed = tuple(c for c in candles if c.closed)
    expected = (source_seconds//step)*step-step
    now_expected = (now_ms//1000//step)*step-step
    if not closed or closed[-1].time != expected or closed[-1].time != now_expected:
        raise MonitorError("STALE_CLOSED_CANDLE")
    if len(closed) < warmup(config.strategy, config.parameters):
        raise MonitorError("INSUFFICIENT_WARMUP")
    if canonical_dataset(config.symbol, config.interval, list(candles))[0] != snapshot.dataset_id:
        raise MonitorError("SNAPSHOT_HASH_MISMATCH")
    return closed


class MonitorService:
    def __init__(self, store: Store, max_age: int = 90):
        if not 1 <= max_age <= 300:
            raise ValueError("Frescor inválido")
        self.store, self.max_age = store, max_age

    def evaluate(self, config: MonitorConfig, now_ms: int | None = None) -> dict:
        use_wall_clock = now_ms is None
        now_ms = int(time.time()*1000) if now_ms is None else now_ms
        snapshot = self.store.load(config.symbol, config.interval)
        if snapshot is None:
            raise MonitorError("SNAPSHOT_NOT_FOUND")
        candles = validated(snapshot, config, now_ms, self.max_age)
        with self.store.connect() as db:
            row = db.execute("SELECT payload FROM datasets WHERE id=?", (snapshot.dataset_id,)).fetchone()
        if not row or hashlib.sha256(row[0].encode("utf-8")).hexdigest() != snapshot.dataset_id:
            raise MonitorError("SNAPSHOT_DATASET_INTEGRITY_ERROR")
        fingerprint = replay_fingerprint()
        if fingerprint["code_hash"] != STARTUP_ENGINE_HASH:
            raise MonitorError("ENGINE_CHANGED_RESTART_REQUIRED")
        definition = {"monitor_version":MONITOR_VERSION, "config":config.model_dump(mode="json"),
                      "engine_hash":fingerprint["code_hash"], "engine_scheme":fingerprint["fingerprint_scheme"]}
        config_hash, _ = digest(definition)
        last = candles[-1]
        with localcontext() as ctx:
            ctx.prec = 34
            ctx.rounding = ROUND_HALF_EVEN
            logic = ResearchStrategy(config.strategy, config.parameters, candles)
            flat, long = logic.decide(len(candles)-1, False), logic.decide(len(candles)-1, True)
            plan = None if flat.action != "buy" or config.strategy == "buy_hold" else {
                "reference_price":decimal_text(last.close),
                "planned_stop":decimal_text(last.close*(Decimal(1)-config.parameters.stop_fraction)),
                "planned_target":decimal_text(last.close*(Decimal(1)+config.parameters.target_fraction)),
                "reward_risk":decimal_text(config.parameters.target_fraction/config.parameters.stop_fraction),
                "invalidation":"Condição válida apenas como hipótese; preço e posição precisam ser reavaliados.",
            }
        signal = {"schema_version":1, "definition":definition, "config_hash":config_hash,
            "dataset_id":snapshot.dataset_id, "candle_time":last.time, "decision_time":last.time+INTERVALS[config.interval],
            "valid_until":last.time+2*INTERVALS[config.interval], "close":decimal_text(last.close),
            "if_flat":flat.model_dump(mode="json"), "if_long":long.model_dump(mode="json"), "plan":plan,
            "mode":"informational_only", "position_checked":False,
            "notice":"Condições hipotéticas; posição, preço executável e elegibilidade não foram verificados."}
        identifier, payload = digest(signal)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Recheck the current snapshot and clock while holding the write lock.
            # A boundary or replacement during evaluation must not yield a stale signal.
            row = db.execute("SELECT payload FROM snapshots WHERE symbol=? AND interval=?",(config.symbol,config.interval)).fetchone()
            if not row:
                raise MonitorError("SNAPSHOT_NOT_FOUND")
            current = Snapshot.model_validate_json(row[0])
            check_time = int(time.time()*1000) if use_wall_clock else now_ms
            current_closed = validated(current,config,check_time,self.max_age)
            if current.dataset_id != snapshot.dataset_id or current_closed[-1].time != last.time:
                raise MonitorError("SNAPSHOT_CHANGED_DURING_EVALUATION")
            prior = db.execute("SELECT id,payload FROM monitor_signals WHERE bot_id=? AND config_hash=? AND candle_time=?",
                               (config.bot_id,config_hash,last.time)).fetchone()
            if prior:
                if hashlib.sha256(prior["payload"].encode()).hexdigest() != prior["id"]:
                    raise MonitorError("SIGNAL_INTEGRITY_ERROR")
                if prior["id"] != identifier or prior["payload"] != payload:
                    raise MonitorError("SIGNAL_CONFLICT")
                return {"id":identifier, **signal}
            previous = db.execute("SELECT candle_time,id,payload FROM monitor_signals WHERE bot_id=? AND config_hash=? ORDER BY candle_time DESC LIMIT 1",
                                  (config.bot_id,config_hash)).fetchone()
            if previous:
                if hashlib.sha256(previous["payload"].encode()).hexdigest() != previous["id"]:
                    raise MonitorError("SIGNAL_INTEGRITY_ERROR")
                if last.time-previous["candle_time"] != INTERVALS[config.interval]:
                    raise MonitorError("MISSED_OR_REWOUND_CANDLES")
            db.execute("INSERT INTO monitor_signals VALUES (?,?,?,?,?)",(identifier,config.bot_id,config_hash,last.time,payload))
        return {"id":identifier, **signal}

    def signals(self, bot_id: str | None = None) -> list[dict]:
        with self.store.connect() as db:
            rows = db.execute("SELECT * FROM monitor_signals"+(" WHERE bot_id=?" if bot_id else "")+
                              " ORDER BY candle_time DESC,id DESC LIMIT 100", (bot_id,) if bot_id else ()).fetchall()
        result = []
        for row in rows:
            if hashlib.sha256(row["payload"].encode()).hexdigest() != row["id"]:
                raise MonitorError("SIGNAL_INTEGRITY_ERROR")
            try:
                value = json.loads(row["payload"])
                if (value["definition"]["config"]["bot_id"] != row["bot_id"] or value["config_hash"] != row["config_hash"]
                    or value["candle_time"] != row["candle_time"] or digest(value["definition"])[0] != row["config_hash"]):
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                raise MonitorError("SIGNAL_INTEGRITY_ERROR") from None
            result.append({"id":row["id"], **value})
        return result
