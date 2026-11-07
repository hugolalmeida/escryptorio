"""Monitor offline: lease com fencing, checkpoint e recuperação histórica causal."""
import hashlib
import json
import time
import uuid
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path

from cryptolab.config import INTERVALS
from cryptolab.engine.strategies import ResearchStrategy, warmup
from cryptolab.history.models import candle_record, decimal_text
from cryptolab.history.reader import DatasetReader
from cryptolab.history.storage import HistoryError, HistoryStore
from cryptolab.models import Snapshot
from cryptolab.monitor.service import MonitorError, MonitorService, STARTUP_ENGINE_HASH, digest, validated
from cryptolab.research.fingerprint import replay_fingerprint

VERSION = "cryptolab-monitor-runtime/1"
LEASE_MS = 120_000
MAX_RECOVERY = 500
MAX_HISTORY = 20_000


def monitor_fingerprint():
    root = Path(__file__).resolve().parent
    files = (root / "runtime.py", root / "service.py", root / "models.py",
             root.parent / "history" / "reader.py", root.parent / "history" / "models.py")
    return digest({"version": VERSION, "files": {p.name if p.parent == root else "history/" + p.name:
        hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest() for p in files}})[0]


STARTUP_MONITOR_HASH = monitor_fingerprint()


class MonitorRuntime:
    def __init__(self, store, max_age=90, clock=None):
        self.store = store
        self.max_age = max_age
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.catalog = MonitorService(store, max_age)

    def definition(self, config):
        fingerprint = replay_fingerprint()
        if fingerprint["code_hash"] != STARTUP_ENGINE_HASH:
            raise MonitorError("ENGINE_CHANGED_RESTART_REQUIRED")
        if monitor_fingerprint() != STARTUP_MONITOR_HASH:
            raise MonitorError("MONITOR_CHANGED_RESTART_REQUIRED")
        return {"monitor_version": VERSION, "monitor_hash": STARTUP_MONITOR_HASH,
                "config": config.model_dump(mode="json"), "engine_hash": fingerprint["code_hash"],
                "engine_scheme": fingerprint["fingerprint_scheme"]}

    def claim(self, config):
        definition = self.definition(config)
        key, payload = digest(definition)
        scope = digest(definition["config"])[0]
        now, owner = self.clock(), uuid.uuid4().hex
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM monitor_runtime WHERE config_hash=?", (key,)).fetchone()
            lease = db.execute("SELECT * FROM monitor_leases WHERE scope_hash=?", (scope,)).fetchone()
            if lease and lease["until_ms"] > now:
                raise MonitorError("MONITOR_LEASE_BUSY")
            if row and row["definition"] != payload:
                raise MonitorError("MONITOR_RUNTIME_INTEGRITY_ERROR")
            # Verify all indexed signals while deriving the latest compatible checkpoint,
            # including legacy records and previous monitor/engine versions.
            prior = None
            rows = db.execute("SELECT * FROM monitor_signals WHERE bot_id=? ORDER BY candle_time DESC,id DESC", (config.bot_id,)).fetchall()
            for signal_row in rows:
                try:
                    if hashlib.sha256(signal_row["payload"].encode()).hexdigest() != signal_row["id"]:
                        raise ValueError()
                    signal = json.loads(signal_row["payload"])
                    d = signal["definition"]
                    if (digest(d)[0] != signal_row["config_hash"] or signal["candle_time"] != signal_row["candle_time"]
                        or d["config"]["bot_id"] != signal_row["bot_id"] or signal["config_hash"] != signal_row["config_hash"]):
                        raise ValueError()
                except (ValueError, KeyError, TypeError):
                    raise MonitorError("SIGNAL_INTEGRITY_ERROR") from None
                if prior is None and d.get("config") == definition["config"]:
                    prior = signal_row["candle_time"]
            if row and row["last_candle"] != prior:
                raise MonitorError("MONITOR_CHECKPOINT_INTEGRITY_ERROR")
            if not row:
                db.execute("INSERT INTO monitor_runtime(config_hash,bot_id,definition,last_candle,state) VALUES (?,?,?,?,?)",
                           (key, config.bot_id, payload, prior, "idle"))
            db.execute("UPDATE monitor_runtime SET lease_owner=?,lease_until_ms=?,state='running',error_code=NULL WHERE config_hash=?",
                       (owner, now + LEASE_MS, key))
            db.execute("INSERT INTO monitor_leases VALUES (?,?,?) ON CONFLICT(scope_hash) DO UPDATE SET owner=excluded.owner,until_ms=excluded.until_ms",
                       (scope, owner, now + LEASE_MS))
        return key, owner, definition

    def _owned(self, db, key, owner):
        row = db.execute("SELECT * FROM monitor_runtime WHERE config_hash=? AND lease_owner=? AND lease_until_ms>?",
                         (key, owner, self.clock())).fetchone()
        if row is None:
            raise MonitorError("MONITOR_LEASE_LOST")
        scope = digest(json.loads(row["definition"])["config"])[0]
        if not db.execute("SELECT 1 FROM monitor_leases WHERE scope_hash=? AND owner=? AND until_ms>?", (scope, owner, self.clock())).fetchone():
            raise MonitorError("MONITOR_LEASE_LOST")
        return row

    def release(self, key, owner, error=None):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM monitor_leases WHERE owner=?", (owner,))
            db.execute("""UPDATE monitor_runtime SET lease_owner=NULL,lease_until_ms=NULL,
                state=?,error_code=?,last_evaluation_ms=? WHERE config_hash=? AND lease_owner=?""",
                ("error" if error else "idle", error, self.clock(), key, owner))

    def _signal(self, config, definition, key, candles, dataset_id, kind):
        last = candles[-1]
        with localcontext() as ctx:
            ctx.prec, ctx.rounding = 34, ROUND_HALF_EVEN
            logic = ResearchStrategy(config.strategy, config.parameters, candles)
            flat, long = logic.decide(len(candles)-1, False), logic.decide(len(candles)-1, True)
            plan = None if flat.action != "buy" or config.strategy == "buy_hold" else {
                "reference_price": decimal_text(last.close),
                "planned_stop": decimal_text(last.close*(Decimal(1)-config.parameters.stop_fraction)),
                "planned_target": decimal_text(last.close*(Decimal(1)+config.parameters.target_fraction)),
                "reward_risk": decimal_text(config.parameters.target_fraction/config.parameters.stop_fraction),
                "invalidation": "Hipótese informativa; preço e posição precisam ser reavaliados."}
        signal = {"schema_version": 2, "definition": definition, "config_hash": key,
                  "dataset_id": dataset_id, "candle_time": last.time,
                  "decision_time": last.time+INTERVALS[config.interval],
                  "valid_until": last.time+2*INTERVALS[config.interval], "close": decimal_text(last.close),
                  "if_flat": flat.model_dump(mode="json"), "if_long": long.model_dump(mode="json"),
                  "plan": plan, "mode": "informational_only", "position_checked": False,
                  "origin": kind, "eligible_for_future_paper_analysis": kind == "current",
                  "notice": "Informativo; não é ordem nem autorização de execução. Valide frescor e posição novamente."}
        return signal

    def once(self, config, recovery_dataset=None):
        key, owner, definition = self.claim(config)
        error = None
        try:
            snapshot = self.store.load(config.symbol, config.interval)
            if snapshot is None:
                raise MonitorError("SNAPSHOT_NOT_FOUND")
            candles = validated(snapshot, config, self.clock(), self.max_age)
            with self.store.connect() as db:
                self._owned(db, key, owner)
                stored = db.execute("SELECT payload FROM datasets WHERE id=?", (snapshot.dataset_id,)).fetchone()
                cursor = db.execute("SELECT last_candle FROM monitor_runtime WHERE config_hash=?", (key,)).fetchone()[0]
            if not stored or hashlib.sha256(stored[0].encode()).hexdigest() != snapshot.dataset_id:
                raise MonitorError("SNAPSHOT_DATASET_INTEGRITY_ERROR")
            step, latest = INTERVALS[config.interval], candles[-1].time
            if cursor is not None and latest < cursor:
                raise MonitorError("CANDLE_REWOUND")
            pending = []
            if cursor is not None and latest - cursor > step:
                count = (latest-cursor)//step-1
                if count > MAX_RECOVERY:
                    raise MonitorError("RECOVERY_LIMIT_EXCEEDED")
                if not recovery_dataset:
                    raise MonitorError("RECOVERY_DATASET_REQUIRED")
                try:
                    history = DatasetReader(HistoryStore(self.store.path)).read(recovery_dataset)
                except HistoryError as exc:
                    raise MonitorError(str(exc)) from None
                if (history.manifest["symbol"] != config.symbol or history.manifest["interval"] != config.interval
                    or len(history.candles) > MAX_HISTORY or history.start_time > cursor
                    or history.end_time < latest):
                    raise MonitorError("RECOVERY_DATASET_RANGE_INVALID")
                by_time = {c.time: c for c in history.candles}
                # Anchor the recovered series to the immutable candle behind the checkpoint.
                with self.store.connect() as db:
                    anchor_rows = db.execute("SELECT payload FROM monitor_signals WHERE bot_id=? AND candle_time=? ORDER BY id",
                                             (config.bot_id, cursor)).fetchall()
                    anchor = next((json.loads(r[0]) for r in anchor_rows
                                   if json.loads(r[0])["definition"]["config"] == definition["config"]), None)
                    source = db.execute("SELECT payload FROM datasets WHERE id=?", (anchor["dataset_id"],)).fetchone() if anchor else None
                if not source or hashlib.sha256(source[0].encode()).hexdigest() != anchor["dataset_id"]:
                    raise MonitorError("RECOVERY_ANCHOR_INTEGRITY_ERROR")
                source_candles = json.loads(source[0])["candles"]
                original = next((c for c in source_candles if c["time"] == cursor), None)
                if not original or cursor not in by_time:
                    raise MonitorError("RECOVERY_ANCHOR_INTEGRITY_ERROR")
                from cryptolab.models import Candle
                if candle_record(Candle.model_validate(original)) != candle_record(by_time[cursor]):
                    raise MonitorError("RECOVERY_CANDLE_CONFLICT")
                # Any overlapping public records must agree, including the last checkpoint.
                if any(c.time in by_time and c != by_time[c.time] for c in candles):
                    raise MonitorError("RECOVERY_CANDLE_CONFLICT")
                for stamp in range(cursor+step, latest, step):
                    end = (stamp-history.start_time)//step+1
                    prefix = history.candles[:end]
                    if len(prefix) < warmup(config.strategy, config.parameters) or not prefix or prefix[-1].time != stamp:
                        raise MonitorError("RECOVERY_INSUFFICIENT_WARMUP")
                    pending.append(self._signal(config, definition, key, prefix, history.reference_hash, "historical_recovered"))
            pending.append(self._signal(config, definition, key, candles, snapshot.dataset_id, "current"))
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                self._owned(db, key, owner)
                if self.definition(config) != definition:
                    raise MonitorError("MONITOR_CHANGED_RESTART_REQUIRED")
                row = db.execute("SELECT payload FROM snapshots WHERE symbol=? AND interval=?", (config.symbol, config.interval)).fetchone()
                if not row:
                    raise MonitorError("SNAPSHOT_NOT_FOUND")
                current = Snapshot.model_validate_json(row[0])
                if validated(current, config, self.clock(), self.max_age)[-1].time != latest or current.dataset_id != snapshot.dataset_id:
                    raise MonitorError("SNAPSHOT_CHANGED_DURING_EVALUATION")
                stored = db.execute("SELECT payload FROM datasets WHERE id=?", (current.dataset_id,)).fetchone()
                if not stored or hashlib.sha256(stored[0].encode()).hexdigest() != current.dataset_id:
                    raise MonitorError("SNAPSHOT_DATASET_INTEGRITY_ERROR")
                for signal in pending:
                    identifier, payload = digest(signal)
                    old = db.execute("SELECT id,payload FROM monitor_signals WHERE bot_id=? AND config_hash=? AND candle_time=?",
                                     (config.bot_id, key, signal["candle_time"])).fetchone()
                    if old and (old["id"] != identifier or old["payload"] != payload):
                        raise MonitorError("SIGNAL_CONFLICT")
                    if not old:
                        db.execute("INSERT INTO monitor_signals VALUES (?,?,?,?,?)", (identifier, config.bot_id, key, signal["candle_time"], payload))
                self._owned(db, key, owner)
                db.execute("UPDATE monitor_runtime SET last_candle=?,last_evaluation_ms=?,error_code=NULL WHERE config_hash=? AND lease_owner=?",
                           (latest, self.clock(), key, owner))
            signal = pending[-1]
            return {"id": digest(signal)[0], **signal}
        except MonitorError as exc:
            error = str(exc)
            raise
        except BaseException:
            error = "MONITOR_INTERRUPTED"
            raise
        finally:
            self.release(key, owner, error)

    def status(self, bot=None):
        with self.store.connect() as db:
            rows = db.execute("SELECT * FROM monitor_runtime" + (" WHERE bot_id=?" if bot else "") + " ORDER BY bot_id,config_hash", (bot,) if bot else ()).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                definition = json.loads(item.pop("definition"))
                if digest(definition)[0] != item["config_hash"] or definition["config"]["bot_id"] != item["bot_id"]:
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                raise MonitorError("MONITOR_RUNTIME_INTEGRITY_ERROR") from None
            item["definition"] = definition
            item["lease_active"] = bool(item["lease_owner"] and item["lease_until_ms"] > self.clock())
            if item["state"] == "running" and not item["lease_active"]:
                item["state"] = "lease_expired"
            item.pop("lease_owner")
            result.append(item)
        return result

    def loop(self, config, poll_seconds=15, recovery_dataset=None, sleeper=time.sleep, emit=print):
        if not 10 <= poll_seconds <= 60:
            raise ValueError("Polling deve estar entre 10 e 60 segundos")
        try:
            while True:
                try:
                    emit(json.dumps(self.once(config, recovery_dataset), ensure_ascii=True))
                except MonitorError as exc:
                    emit(json.dumps({"error": str(exc)}, ensure_ascii=True))
                sleeper(poll_seconds)
        except KeyboardInterrupt:
            return
