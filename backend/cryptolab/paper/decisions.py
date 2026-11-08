"""Vínculos e decisões auditáveis. Não escreve no ledger nem executa operações."""
import json
import re
import sqlite3
import time
from decimal import localcontext
from functools import wraps

from cryptolab.history.models import canonical_json
from cryptolab.monitor.models import MonitorConfig
from cryptolab.monitor.runtime import MonitorRuntime
from cryptolab.monitor.service import MonitorError, digest
from cryptolab.models import Snapshot
from cryptolab.paper.ledger import LEDGER_CONTEXT
from cryptolab.paper.planner import (VERSION as PLANNER_VERSION, MarketValidator, PlannerError,
                                     SignalValidator, VirtualTradePlanner, WalletValidator)
from cryptolab.paper.planner_models import PlannerBinding
from cryptolab.paper.storage import PaperError, PaperStore
from cryptolab.storage import Store, canonical_dataset

VERSION = "cryptolab-paper-decisions/1"


class DecisionError(ValueError):
    pass


def _database_errors(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except sqlite3.Error:
            raise DecisionError("DECISION_DATABASE_ERROR") from None
    return checked


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise DecisionError("INVALID_IDENTIFIER")
    return value


def _reason(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value):
        raise DecisionError("INVALID_REASON_CODE")
    return value


class DecisionService:
    def __init__(self, path, max_age=90, clock=None):
        self.store = Store(path)
        self.paper = PaperStore(path)
        self.planner = VirtualTradePlanner(path, max_age, clock)
        self.max_age = max_age
        self.clock = clock or (lambda: int(time.time()*1000))

    def _time(self, db):
        now = self.clock()
        if type(now) is not int or now < 0:
            raise DecisionError("INVALID_CLOCK")
        row = db.execute("SELECT high_water_ms FROM paper_decision_clock WHERE id=1").fetchone()
        if not row or now < row[0]:
            raise DecisionError("CLOCK_ROLLBACK")
        db.execute("UPDATE paper_decision_clock SET high_water_ms=? WHERE id=1", (now,))
        return now

    @staticmethod
    def _event(db, entity, identifier, kind, now, reason=None):
        table = "paper_binding" if entity == "binding" else "paper_decision"
        key = "binding_id" if entity == "binding" else "decision_id"
        head = db.execute(f"SELECT * FROM {table}_heads WHERE {key}=?", (identifier,)).fetchone()
        seq = head["sequence"]+1 if head else 1
        previous = head["event_hash"] if head else identifier
        body = {"schema_version":1, "entity":entity, "id":identifier, "sequence":seq,
                "kind":kind, "at_ms":now, "reason":reason, "previous_hash":previous}
        event_hash, payload = digest(body)
        db.execute(f"INSERT INTO {table}_events VALUES (?,?,?,?,?,?)", (identifier,seq,kind,payload,previous,event_hash))
        if head:
            db.execute(f"UPDATE {table}_heads SET sequence=?,event_hash=?,state=? WHERE {key}=?", (seq,event_hash,kind,identifier))
        else:
            db.execute(f"INSERT INTO {table}_heads VALUES (?,?,?,?)", (identifier,seq,event_hash,kind))

    @staticmethod
    def _events(db, entity, identifier):
        table = "paper_binding" if entity == "binding" else "paper_decision"
        key = "binding_id" if entity == "binding" else "decision_id"
        head = db.execute(f"SELECT * FROM {table}_heads WHERE {key}=?", (identifier,)).fetchone()
        rows = db.execute(f"SELECT * FROM {table}_events WHERE {key}=? ORDER BY sequence", (identifier,)).fetchall()
        if not head or not rows or len(rows) != head["sequence"]:
            raise DecisionError("CHECKPOINT_INTEGRITY_ERROR")
        previous, events, state, timestamp = identifier, [], None, -1
        allowed = {"binding": {None:{"REGISTERED"}, "REGISTERED":{"ACTIVE","DISABLED"}, "ACTIVE":{"DISABLED"}, "DISABLED":set()},
                   "decision": {None:{"RECORDED"}, "RECORDED":{"INVALIDATED","EXPIRED"}, "INVALIDATED":set(), "EXPIRED":set()}}[entity]
        for seq, row in enumerate(rows, 1):
            try:
                body = json.loads(row["payload"])
                if (digest(body) != (row["event_hash"],row["payload"]) or row["sequence"] != seq
                    or body != {"schema_version":1,"entity":entity,"id":identifier,"sequence":seq,"kind":row["kind"],
                                "at_ms":body["at_ms"],"reason":body["reason"],"previous_hash":previous}
                    or row["previous_hash"] != previous or row["kind"] not in allowed[state]
                    or type(body["at_ms"]) is not int or body["at_ms"] < timestamp
                    or (seq == 1 and body["reason"] is not None) or (seq > 1 and body["reason"] is None)
                    or (body["reason"] is not None and _reason(body["reason"]) != body["reason"])):
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                raise DecisionError("EVENT_INTEGRITY_ERROR") from None
            previous, state, timestamp = row["event_hash"], row["kind"], body["at_ms"]
            events.append({"event_hash":previous, **body})
        if head["event_hash"] != previous or head["state"] != state:
            raise DecisionError("CHECKPOINT_INTEGRITY_ERROR")
        return events

    def _binding(self, db, identifier):
        row = db.execute("SELECT * FROM paper_bindings WHERE id=?", (_identifier(identifier),)).fetchone()
        if not row:
            raise DecisionError("BINDING_NOT_FOUND")
        try:
            value = json.loads(row["payload"])
            binding = PlannerBinding.model_validate(value["binding"])
            if (digest(value) != (identifier,row["payload"]) or value["schema_version"] != 1
                or value["service_version"] != VERSION or value["wallet_id"] != row["wallet_id"]
                or value["bot_id"] != row["bot_id"] or value["version"] != row["version"]
                or value["monitor_config_hash"] != row["config_hash"] or binding.wallet_id != row["wallet_id"]
                or binding.monitor_config_hash != row["config_hash"]
                or digest(value["monitor_definition"])[0] != row["config_hash"]
                or value["monitor_definition"]["config"]["bot_id"] != row["bot_id"]
                or value["wallet_hash"] != binding.wallet_hash
                or value["financial_fingerprint"] != value["monitor_definition"]["engine_hash"]
                or not isinstance(value["planner_version"], str) or type(value["created_at_ms"]) is not int):
                raise ValueError()
            config = MonitorConfig.model_validate(value["monitor_definition"]["config"])
            if any(value[k] != getattr(config,k) for k in ("bot_id","strategy","strategy_version","symbol","interval")):
                raise ValueError()
            wallet, _ = self.paper._replay(db,row["wallet_id"])
            if wallet["wallet_hash"] != binding.wallet_hash or any(wallet["spec"][k] != getattr(config,k) for k in ("bot_id","strategy","strategy_version","symbol","interval")):
                raise ValueError()
            runtime = db.execute("SELECT definition,bot_id FROM monitor_runtime WHERE config_hash=?", (row["config_hash"],)).fetchone()
            if not runtime or runtime["definition"] != canonical_json(value["monitor_definition"]) or runtime["bot_id"] != row["bot_id"]:
                raise ValueError()
        except (KeyError, ValueError, TypeError, PaperError):
            raise DecisionError("BINDING_INTEGRITY_ERROR") from None
        events = self._events(db, "binding", identifier)
        if events[0]["at_ms"] != value["created_at_ms"]:
            raise DecisionError("BINDING_INTEGRITY_ERROR")
        active = db.execute("SELECT * FROM paper_binding_active WHERE binding_id=?", (identifier,)).fetchone()
        if (events[-1]["kind"] == "ACTIVE") != bool(active) or (active and (active["wallet_id"] != row["wallet_id"] or active["bot_id"] != row["bot_id"])):
            raise DecisionError("BINDING_PROJECTION_INTEGRITY_ERROR")
        return {"id":identifier, **value, "state":events[-1]["kind"], "events":events}

    def register_binding(self, value: dict) -> dict:
        try:
            binding = PlannerBinding.model_validate(value)
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                now = self._time(db)
                wallet, _ = self.paper._replay(db, binding.wallet_id)
                if wallet["wallet_hash"] != binding.wallet_hash:
                    raise DecisionError("BINDING_WALLET_MISMATCH")
                runtime = db.execute("SELECT * FROM monitor_runtime WHERE config_hash=?", (binding.monitor_config_hash,)).fetchone()
                if not runtime:
                    raise DecisionError("MONITOR_CONFIG_NOT_FOUND")
                definition = json.loads(runtime["definition"])
                config = MonitorConfig.model_validate(definition["config"])
                if (digest(definition)[0] != binding.monitor_config_hash or runtime["bot_id"] != config.bot_id
                    or MonitorRuntime(self.store).definition(config) != definition):
                    raise DecisionError("MONITOR_CONFIG_INCOMPATIBLE")
                if any(wallet["spec"][k] != getattr(config,k) for k in ("bot_id","strategy","strategy_version","symbol","interval")):
                    raise DecisionError("WALLET_CONFIG_MISMATCH")
                rows = db.execute("SELECT id FROM paper_bindings WHERE wallet_id=? ORDER BY version", (binding.wallet_id,)).fetchall()
                existing = [self._binding(db, r[0]) for r in rows]
                for item in existing:
                    if item["state"] != "DISABLED" and item["binding"] == binding.model_dump(mode="json") and item["monitor_definition"] == definition:
                        return item
                version = max((item["version"] for item in existing), default=0)+1
                body = {"schema_version":1,"service_version":VERSION,"version":version,"created_at_ms":now,
                        "wallet_id":binding.wallet_id,"wallet_hash":binding.wallet_hash,"bot_id":config.bot_id,
                        "strategy":config.strategy,"strategy_version":config.strategy_version,"symbol":config.symbol,
                        "interval":config.interval,"monitor_config_hash":binding.monitor_config_hash,"monitor_definition":definition,
                        "financial_fingerprint":definition["engine_hash"],"planner_version":PLANNER_VERSION,
                        "binding":binding.model_dump(mode="json")}
                identifier,payload = digest(body)
                db.execute("INSERT INTO paper_bindings VALUES (?,?,?,?,?,?)", (identifier,binding.wallet_id,config.bot_id,version,binding.monitor_config_hash,payload))
                self._event(db,"binding",identifier,"REGISTERED",now)
                return self._binding(db, identifier)
        except DecisionError:
            raise
        except (PaperError, PlannerError, MonitorError) as exc:
            raise DecisionError(str(exc)) from None
        except (ValueError, KeyError, TypeError, sqlite3.Error):
            raise DecisionError("BINDING_INVALID") from None

    def _transition_binding(self, identifier, target, reason):
        reason = _reason(reason)
        try:
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                now = self._time(db)
                item = self._binding(db, identifier)
                state = item["state"]
                if state == target:
                    if item["events"][-1]["reason"] != reason:
                        raise DecisionError("BINDING_TRANSITION_CONFLICT")
                    return item
                if target == "ACTIVE":
                    if state != "REGISTERED":
                        raise DecisionError("BINDING_TRANSITION_INVALID")
                    if item["planner_version"] != PLANNER_VERSION:
                        raise DecisionError("PLANNER_VERSION_INCOMPATIBLE")
                    config = MonitorConfig.model_validate(item["monitor_definition"]["config"])
                    if MonitorRuntime(self.store).definition(config) != item["monitor_definition"]:
                        raise DecisionError("MONITOR_CONFIG_INCOMPATIBLE")
                    other = db.execute("""SELECT 1 FROM monitor_runtime WHERE bot_id=? AND config_hash<>?
                        AND lease_owner IS NOT NULL AND lease_until_ms>? LIMIT 1""",
                        (item["bot_id"],item["monitor_config_hash"],now)).fetchone()
                    if other:
                        raise DecisionError("AMBIGUOUS_BOT_CONFIG")
                    self.paper._replay(db,item["wallet_id"])
                    db.execute("INSERT INTO paper_binding_active VALUES (?,?,?)", (item["wallet_id"],item["bot_id"],identifier))
                elif target == "DISABLED":
                    if state not in ("REGISTERED","ACTIVE"):
                        raise DecisionError("BINDING_TRANSITION_INVALID")
                    db.execute("DELETE FROM paper_binding_active WHERE binding_id=?", (identifier,))
                else:
                    raise DecisionError("BINDING_TRANSITION_INVALID")
                self._event(db,"binding",identifier,target,now,reason)
                return self._binding(db,identifier)
        except DecisionError:
            raise
        except sqlite3.IntegrityError:
            raise DecisionError("BINDING_ACTIVE_CONFLICT") from None
        except sqlite3.Error:
            raise DecisionError("DECISION_DATABASE_ERROR") from None
        except (PaperError, PlannerError, MonitorError) as exc:
            raise DecisionError(str(exc)) from None

    def activate_binding(self, identifier: str, reason: str = "MANUAL_ACTIVATION") -> dict:
        return self._transition_binding(identifier,"ACTIVE",reason)

    def disable_binding(self, identifier: str, reason: str) -> dict:
        return self._transition_binding(identifier,"DISABLED",reason)

    @_database_errors
    def get_binding(self, identifier: str) -> dict:
        with self.store.connect() as db:
            db.execute("BEGIN")
            return self._binding(db,identifier)

    @_database_errors
    def list_bindings(self) -> list[dict]:
        with self.store.connect() as db:
            db.execute("BEGIN")
            return [self._binding(db,r[0]) for r in db.execute("SELECT id FROM paper_bindings ORDER BY wallet_id,version").fetchall()]

    def _decision(self, db, identifier):
        row = db.execute("SELECT * FROM paper_decisions WHERE id=?", (_identifier(identifier),)).fetchone()
        if not row:
            raise DecisionError("DECISION_NOT_FOUND")
        try:
            body = json.loads(row["payload"])
            p = body["proposal"]
            if (digest(body) != (identifier,row["payload"]) or body["schema_version"] != 1 or body["service_version"] != VERSION
                or any(body[k] != row[k] for k in ("wallet_id","binding_id","signal_id","config_hash","candle_time"))
                or p["signal_id"] != row["signal_id"] or p["wallet_id"] != row["wallet_id"]
                or p["monitor_config_hash"] != row["config_hash"] or p["decision_candle"] != row["candle_time"]
                or digest({k:v for k,v in p.items() if k != "validation_hash"})[0] != p["validation_hash"]
                or p["execution_enabled"] is not False or body["signal_hash"] != row["signal_id"]
                or digest(body["market_snapshot"]["instrument"])[0] != p["instrument_hash"]):
                raise ValueError()
            binding = self._binding(db,row["binding_id"])
            if (binding["wallet_id"] != row["wallet_id"] or binding["monitor_config_hash"] != row["config_hash"]
                or body["binding_version"] != binding["version"] or p["binding_hash"] != digest(binding["binding"])[0]
                or p["planner_version"] != binding["planner_version"]):
                raise ValueError()
            signal = db.execute("SELECT * FROM monitor_signals WHERE id=?", (row["signal_id"],)).fetchone()
            if (not signal or digest(json.loads(signal["payload"])) != (row["signal_id"],signal["payload"])
                or signal["config_hash"] != row["config_hash"] or signal["candle_time"] != row["candle_time"]):
                raise ValueError()
            snapshot = Snapshot.model_validate(body["market_snapshot"])
            if (digest(body["market_snapshot"])[0] != p["snapshot_hash"] or snapshot.dataset_id != p["dataset_id"] or canonical_dataset(snapshot.symbol,snapshot.interval,snapshot.candles)[0] != snapshot.dataset_id
                or snapshot.ticker.source_time_ms != p["ticker_source_time_ms"] or snapshot.source_time_ms != p["market_source_time_ms"]):
                raise ValueError()
            _, ledger = self.paper._replay(db,row["wallet_id"])
            seq = p["wallet_sequence"]
            if type(seq) is not int or not 1 <= seq <= len(ledger) or ledger[seq-1]["event_hash"] != p["wallet_head_hash"]:
                raise ValueError()
        except (KeyError, ValueError, TypeError, PaperError):
            raise DecisionError("DECISION_INTEGRITY_ERROR") from None
        events = self._events(db,"decision",identifier)
        if events[0]["at_ms"] != body["registered_at_ms"]:
            raise DecisionError("DECISION_INTEGRITY_ERROR")
        return {"id":identifier, **body, "state":events[-1]["kind"], "events":events}

    def record_decision(self, binding_id: str, signal_id: str, expected_validation_hash: str) -> dict:
        _identifier(binding_id); _identifier(signal_id); _identifier(expected_validation_hash)
        try:
            # Commit observed time and expiration even if the subsequent request
            # is rejected. Otherwise rollback could erase an observed expiry.
            expired = self._observe_expiry(binding_id, signal_id)
            if expired:
                raise DecisionError("DECISION_EXPIRED")
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                now = self._time(db)
                binding = self._binding(db,binding_id)
                if binding["state"] != "ACTIVE":
                    raise DecisionError("BINDING_NOT_ACTIVE")
                if binding["planner_version"] != PLANNER_VERSION:
                    raise DecisionError("PLANNER_VERSION_INCOMPATIBLE")
                contract = PlannerBinding.model_validate(binding["binding"])
                proposal, snapshot = self._calculate(db, contract, signal_id, now)
                if proposal["validation_hash"] != expected_validation_hash:
                    raise DecisionError("PROPOSAL_CHANGED")
                if proposal["status"] not in ("HOLD","CONDITIONAL_REVALIDATION_REQUIRED"):
                    raise DecisionError("PROPOSAL_NOT_RECORDABLE")
                row = db.execute("SELECT id FROM paper_decisions WHERE wallet_id=? AND candle_time=?", (contract.wallet_id,proposal["decision_candle"])).fetchone()
                if row:
                    old = self._decision(db,row[0])
                    if old["binding_id"] != binding_id or old["signal_id"] != signal_id or old["proposal"] != proposal:
                        raise DecisionError("DECISION_CONFLICT")
                    if old["state"] != "RECORDED":
                        raise DecisionError("DECISION_NOT_CURRENT")
                    check = self._time(db)
                    latest, _ = self._calculate(db,contract,signal_id,check)
                    if latest != proposal:
                        raise DecisionError("PROPOSAL_CHANGED")
                    return old
                body = {"schema_version":1,"service_version":VERSION,"registered_at_ms":now,
                        "wallet_id":contract.wallet_id,"binding_id":binding_id,"binding_version":binding["version"],
                        "signal_id":signal_id,"signal_hash":signal_id,"config_hash":contract.monitor_config_hash,
                        "candle_time":proposal["decision_candle"],"proposal":proposal,
                        "market_snapshot":snapshot.model_dump(mode="json")}
                identifier,payload = digest(body)
                db.execute("INSERT INTO paper_decisions VALUES (?,?,?,?,?,?,?)", (identifier,contract.wallet_id,binding_id,signal_id,contract.monitor_config_hash,proposal["decision_candle"],payload))
                self._event(db,"decision",identifier,"RECORDED",now)
                # Recheck actual clock and all premises while the write lock is held.
                check = self._time(db)
                latest, _ = self._calculate(db,contract,signal_id,check)
                if latest != proposal:
                    raise DecisionError("PROPOSAL_CHANGED")
                return self._decision(db,identifier)
        except DecisionError:
            raise
        except (PlannerError, PaperError) as exc:
            raise DecisionError(str(exc)) from None
        except sqlite3.IntegrityError:
            raise DecisionError("DECISION_CONFLICT") from None
        except sqlite3.Error:
            raise DecisionError("DECISION_DATABASE_ERROR") from None

    def _observe_expiry(self, binding_id: str, signal_id: str) -> bool:
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self._time(db)
            binding = self._binding(db,binding_id)
            signal = db.execute("SELECT candle_time FROM monitor_signals WHERE id=?", (signal_id,)).fetchone()
            row = db.execute("SELECT id FROM paper_decisions WHERE wallet_id=? AND candle_time=?",
                             (binding["wallet_id"],signal["candle_time"])).fetchone() if signal else None
            if row:
                item = self._decision(db,row["id"])
                if item["state"] == "RECORDED" and now >= item["proposal"]["expires_at"]*1000:
                    self._event(db,"decision",item["id"],"EXPIRED",now,"SIGNAL_EXPIRED")
                    return True
                return item["state"] == "EXPIRED"
            return False

    def _calculate(self, db, binding, signal_id, now):
        signal, config = SignalValidator(self.store).validate(db,signal_id,binding,now)
        wallet = WalletValidator(self.store).validate(db,binding.wallet_id,binding,config)
        snapshot,rules = MarketValidator(self.max_age).validate(db,signal,config,now)
        with localcontext(LEDGER_CONTEXT):
            proposal = self.planner._propose(signal_id,signal,config,wallet,snapshot,rules,binding,now)
        return proposal,snapshot

    @_database_errors
    def get_decision(self, identifier: str) -> dict:
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self._time(db)
            item = self._decision(db,identifier)
            if item["state"] == "RECORDED" and now >= item["proposal"]["expires_at"]*1000:
                self._event(db,"decision",identifier,"EXPIRED",now,"SIGNAL_EXPIRED")
                item = self._decision(db,identifier)
            return item

    @_database_errors
    def invalidate_decision(self, identifier: str, reason: str) -> dict:
        _reason(reason)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self._time(db)
            item = self._decision(db,identifier)
            if item["state"] == "RECORDED":
                kind = "EXPIRED" if now >= item["proposal"]["expires_at"]*1000 else "INVALIDATED"
                self._event(db,"decision",identifier,kind,now,"SIGNAL_EXPIRED" if kind == "EXPIRED" else reason)
                item = self._decision(db,identifier)
            elif item["state"] == "INVALIDATED" and item["events"][-1]["reason"] != reason:
                raise DecisionError("DECISION_INVALIDATION_CONFLICT")
            return item

    @_database_errors
    def verify_integrity(self) -> dict:
        with self.store.connect() as db:
            db.execute("BEGIN")
            bindings = [self._binding(db,r[0]) for r in db.execute("SELECT id FROM paper_bindings").fetchall()]
            decisions = [self._decision(db,r[0]) for r in db.execute("SELECT id FROM paper_decisions").fetchall()]
            active = db.execute("SELECT COUNT(*) FROM paper_binding_active").fetchone()[0]
            if active != sum(b["state"] == "ACTIVE" for b in bindings):
                raise DecisionError("BINDING_PROJECTION_INTEGRITY_ERROR")
            if (db.execute("PRAGMA foreign_key_check").fetchone()
                or db.execute("SELECT COUNT(*) FROM paper_binding_heads").fetchone()[0] != len(bindings)
                or db.execute("SELECT COUNT(*) FROM paper_decision_heads").fetchone()[0] != len(decisions)):
                raise DecisionError("REFERENTIAL_INTEGRITY_ERROR")
            clock = db.execute("SELECT high_water_ms FROM paper_decision_clock WHERE id=1").fetchone()
            latest = max((event["at_ms"] for item in bindings+decisions for event in item["events"]),default=0)
            if not clock or clock[0] < latest:
                raise DecisionError("CLOCK_CHECKPOINT_INTEGRITY_ERROR")
            return {"valid":True,"bindings":len(bindings),"decisions":len(decisions),"execution_enabled":False}
