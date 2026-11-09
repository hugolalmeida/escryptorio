"""Marcação paper pública e verificada, sem SDK ou operações de corretora."""
import json
import hashlib
import os
import re
import sqlite3

from cryptolab.config import INTERVALS, Settings
from cryptolab.models import Snapshot
from cryptolab.history.models import decimal_text
from cryptolab.monitor.service import MonitorError, digest, validated
from cryptolab.monitor.models import MonitorConfig
from cryptolab.paper.decisions import DecisionError, DecisionService
from cryptolab.paper.executor_models import PaperMarkProvenance
from cryptolab.paper.models import MarkRecord
from cryptolab.paper.planner import VERSION as PLANNER_VERSION, MarketValidator, PlannerError, SignalValidator, WalletValidator
from cryptolab.paper.planner_models import PlannerBinding, reject_float
from cryptolab.paper.storage import PaperError, PaperStore
from cryptolab.storage import Store, canonical_dataset

VERSION = "cryptolab-paper-executor/1"


class ExecutionError(ValueError):
    pass


def guard(paper=False):
    Settings.from_env()  # LIVE_TRADING_ENABLED must remain false.
    if paper and os.getenv("PAPER_SIMULATION_ENABLED", "false").lower() != "true":
        raise ExecutionError("PAPER_SIMULATION_DISABLED")


def validate_candle_numbers(db, config):
    row = db.execute("SELECT payload FROM snapshots WHERE symbol=? AND interval=?",(config.symbol,config.interval)).fetchone()
    if not row:
        raise ExecutionError("SNAPSHOT_NOT_FOUND")
    try:
        reject_float(json.loads(row[0])["candles"])
    except (ValueError,KeyError,TypeError):
        raise ExecutionError("FLOAT_MARKET_DATA_REJECTED") from None


def verify_mark(db, paper, identifier):
    row = db.execute("SELECT * FROM paper_mark_evidence WHERE id=?", (identifier,)).fetchone()
    if not row:
        raise ExecutionError("MARK_NOT_FOUND")
    try:
        body = json.loads(row["payload"])
        evidence = PaperMarkProvenance.model_validate(body)
        if digest(body) != (row["id"],row["payload"]) or evidence.executor_version != VERSION:
            raise ValueError()
        if any(body[k] != row[k] for k in ("wallet_id","binding_id","signal_id","idempotency_key","event_id")):
            raise ValueError()
        if evidence.ticker_source_time_ms != row["source_time_ms"]:
            raise ValueError()
        snapshot = Snapshot.model_validate(evidence.snapshot)
        binding = DecisionService(paper.path)._binding(db,evidence.binding_id)
        config = MonitorConfig.model_validate(binding["monitor_definition"]["config"])
        signal_row = db.execute("SELECT * FROM monitor_signals WHERE id=?",(evidence.signal_id,)).fetchone()
        if not signal_row:
            raise ValueError()
        signal = json.loads(signal_row["payload"])
        if (digest(evidence.snapshot)[0] != evidence.snapshot_hash
            or canonical_dataset(snapshot.symbol,snapshot.interval,snapshot.candles)[0] != snapshot.dataset_id
            or digest(snapshot.instrument)[0] != evidence.instrument_hash
            or digest(signal) != (evidence.signal_id,signal_row["payload"])
            or signal_row["config_hash"] != binding["monitor_config_hash"]
            or signal_row["bot_id"] != binding["bot_id"] or signal["dataset_id"] != snapshot.dataset_id
            or signal["candle_time"] != signal_row["candle_time"] or signal["schema_version"] != 2
            or signal["origin"] != "current" or evidence.wallet_id != binding["wallet_id"]
            or signal.get("eligible_for_future_paper_analysis") is not True
            or signal.get("mode") != "informational_only" or signal.get("position_checked") is not False
            or signal["config_hash"] != binding["monitor_config_hash"]
            or digest(signal["definition"])[0] != binding["monitor_config_hash"]
            or snapshot.symbol != evidence.symbol or snapshot.interval != evidence.interval
            or snapshot.ticker.symbol != evidence.symbol or snapshot.instrument["symbol"] != evidence.symbol
            or snapshot.instrument["status"] != "Trading" or snapshot.instrument["quote_coin"] != "USDT"
            or snapshot.ticker.source_time_ms != evidence.ticker_source_time_ms
            or snapshot.source_time_ms != evidence.market_source_time_ms
            or snapshot.fetched_at_ms != evidence.fetched_at_ms or decimal_text(snapshot.ticker.price) != evidence.price
            or any(stamp > evidence.marked_at_ms or evidence.marked_at_ms-stamp > evidence.max_age_seconds*1000
                   for stamp in (snapshot.ticker.source_time_ms,snapshot.source_time_ms,snapshot.fetched_at_ms,snapshot.instrument["source_time_ms"]))
            or signal["decision_time"] != signal["candle_time"]+INTERVALS[snapshot.interval]
            or signal["valid_until"] != signal["decision_time"]+INTERVALS[snapshot.interval]
            or not signal["decision_time"]*1000 <= evidence.marked_at_ms < signal["valid_until"]*1000
            or evidence.candle_time != signal["decision_time"]
            or evidence.candle_time != (evidence.ticker_source_time_ms//1000//INTERVALS[snapshot.interval])*INTERVALS[snapshot.interval]):
            raise ValueError()
        closed = validated(snapshot,config,evidence.marked_at_ms,evidence.max_age_seconds)
        if closed[-1].time != signal["candle_time"] or not any(c.time == evidence.candle_time and not c.closed for c in snapshot.candles):
            raise ValueError()
        dataset = db.execute("SELECT payload FROM datasets WHERE id=?",(snapshot.dataset_id,)).fetchone()
        if not dataset or hashlib.sha256(dataset[0].encode()).hexdigest() != snapshot.dataset_id:
            raise ValueError()
        _, events = paper._replay(db,evidence.wallet_id)
        event = next(e for e in events if e["event_id"] == evidence.event_id)
        if (event["kind"] != "mark" or event["event_hash"] != evidence.event_hash
            or event["payload"]["input"]["price"] != evidence.price
            or event["payload"]["input"]["candle_time"] != evidence.candle_time
            or event["payload"]["input"]["event_time"] != evidence.marked_at_ms//1000
            or event["idempotency_key"] != "mark-"+digest({"wallet":evidence.wallet_id,"key":evidence.idempotency_key})[0]):
            raise ValueError()
        return {"id":identifier, **body, "ledger_event":event, "receipt_mode":"RECOVER_MARK"}
    except (KeyError,ValueError,TypeError,StopIteration,PaperError,MonitorError,DecisionError):
        raise ExecutionError("MARK_INTEGRITY_ERROR") from None


class PaperMarker:
    def __init__(self, path, max_age=90, clock=None):
        self.store = Store(path)
        self.paper = PaperStore(path)
        self.decisions = DecisionService(path,max_age,clock)
        self.max_age = max_age

    def mark(self, binding_id: str, signal_id: str, idempotency_key: str) -> dict:
        guard(True)
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}",idempotency_key):
            raise ExecutionError("INVALID_IDEMPOTENCY_KEY")
        try:
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                self.decisions._time(db)
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                now = self.decisions._time(db)
                binding = self.decisions._binding(db,binding_id)
                prior = db.execute("SELECT id FROM paper_mark_evidence WHERE wallet_id=? AND idempotency_key=?", (binding["wallet_id"],idempotency_key)).fetchone()
                if prior:
                    receipt = verify_mark(db,self.paper,prior[0])
                    if receipt["binding_id"] != binding_id or receipt["signal_id"] != signal_id:
                        raise ExecutionError("MARK_IDEMPOTENCY_CONFLICT")
                    return receipt
                if binding["state"] != "ACTIVE":
                    raise ExecutionError("BINDING_NOT_ACTIVE")
                contract = PlannerBinding.model_validate(binding["binding"])
                signal, config = SignalValidator(self.store).validate(db,signal_id,contract,now)
                validate_candle_numbers(db,config)
                wallet = WalletValidator(self.store).validate(db,contract.wallet_id,contract,config)
                snapshot,_ = MarketValidator(self.max_age).validate(db,signal,config,now)
                source = snapshot.ticker.source_time_ms
                if (source > now or snapshot.source_time_ms > now or snapshot.fetched_at_ms > now
                    or snapshot.instrument["source_time_ms"] > now):
                    raise ExecutionError("FUTURE_MARKET_CLOCK")
                step = INTERVALS[config.interval]
                candle_time = (source//1000//step)*step
                if not any(c.time == candle_time and not c.closed for c in snapshot.candles):
                    raise ExecutionError("MARK_CANDLE_UNAVAILABLE")
                stamp = now//1000
                if stamp < wallet["state"]["last_event_time"]:
                    raise ExecutionError("MARK_TIME_INVALID")
                old = db.execute("SELECT id FROM paper_mark_evidence WHERE wallet_id=? AND source_time_ms=?",(contract.wallet_id,source)).fetchone()
                if old:
                    raise ExecutionError("MARK_SOURCE_ALREADY_USED")
                key = "mark-"+digest({"wallet":contract.wallet_id,"key":idempotency_key})[0]
                if db.execute("SELECT 1 FROM paper_events WHERE wallet_id=? AND idempotency_key=?",(contract.wallet_id,key)).fetchone():
                    raise ExecutionError("MARK_LEDGER_KEY_CONFLICT")
                event = self.paper.append_in_transaction(db,contract.wallet_id,key,MarkRecord(
                    price=snapshot.ticker.price,candle_time=candle_time,event_time=stamp))
                body = PaperMarkProvenance(executor_version=VERSION,wallet_id=contract.wallet_id,binding_id=binding_id,
                    signal_id=signal_id,idempotency_key=idempotency_key,symbol=config.symbol,interval=config.interval,
                    snapshot_hash=digest(snapshot.model_dump(mode="json"))[0],instrument_hash=digest(snapshot.instrument)[0],
                    ticker_source_time_ms=source,market_source_time_ms=snapshot.source_time_ms,
                    fetched_at_ms=snapshot.fetched_at_ms,marked_at_ms=now,max_age_seconds=self.max_age,candle_time=candle_time,
                    price=event["payload"]["input"]["price"],event_id=event["event_id"],event_hash=event["event_hash"],
                    snapshot=snapshot.model_dump(mode="json")).model_dump(mode="json")
                identifier,payload = digest(body)
                db.execute("INSERT INTO paper_mark_evidence VALUES (?,?,?,?,?,?,?,?)",(identifier,contract.wallet_id,
                    binding_id,signal_id,event["event_id"],source,idempotency_key,payload))
                check = self.decisions._time(db)
                latest_signal, latest_config = SignalValidator(self.store).validate(db,signal_id,contract,check)
                latest, _ = MarketValidator(self.max_age).validate(db,latest_signal,latest_config,check)
                if digest(latest.model_dump(mode="json"))[0] != body["snapshot_hash"]:
                    raise ExecutionError("MARKET_CHANGED")
                receipt=verify_mark(db,self.paper,identifier)
                final = self.decisions._time(db)
                final_signal, final_config = SignalValidator(self.store).validate(db,signal_id,contract,final)
                MarketValidator(self.max_age).validate(db,final_signal,final_config,final)
                guard(True)
                receipt["receipt_mode"]="NEW_MARK"
                return receipt
        except ExecutionError:
            raise
        except (DecisionError,PaperError,PlannerError) as exc:
            raise ExecutionError(str(exc)) from None
        except sqlite3.Error:
            raise ExecutionError("PAPER_DATABASE_ERROR") from None
        except (ValueError,ArithmeticError):
            raise ExecutionError("MARK_INPUT_INVALID") from None


def validate_for_execution(db, decisions, identifier, now):
    """Read and validate an unconsumed decision inside the caller's transaction."""
    decision = decisions._decision(db,identifier)
    proposal = decision["proposal"]
    if decision["state"] != "RECORDED":
        raise ExecutionError("DECISION_NOT_RECORDED")
    if now >= proposal["expires_at"]*1000:
        raise ExecutionError("DECISION_EXPIRED")
    if proposal["action"] not in ("BUY","SELL"):
        raise ExecutionError("HOLD_NOT_EXECUTABLE")
    if proposal["status"] != "CONDITIONAL_REVALIDATION_REQUIRED":
        raise ExecutionError("DECISION_NOT_ELIGIBLE")
    binding = decisions._binding(db,decision["binding_id"])
    if binding["state"] != "ACTIVE":
        raise ExecutionError("BINDING_NOT_ACTIVE")
    if binding["planner_version"] != PLANNER_VERSION:
        raise ExecutionError("PLANNER_VERSION_INCOMPATIBLE")
    if db.execute("SELECT 1 FROM paper_execution_evidence WHERE decision_id=?",(identifier,)).fetchone():
        raise ExecutionError("DECISION_ALREADY_CONSUMED")
    contract = PlannerBinding.model_validate(binding["binding"])
    validate_candle_numbers(db,MonitorConfig.model_validate(binding["monitor_definition"]["config"]))
    wallet, events = decisions.paper._replay(db,contract.wallet_id)
    if wallet["state"]["state"] != "active":
        raise ExecutionError("WALLET_PAUSED")
    if wallet["sequence"] != proposal["wallet_sequence"] or wallet["head_hash"] != proposal["wallet_head_hash"]:
        raise ExecutionError("LEDGER_CHANGED")
    if now < proposal["earliest_fill_candle"]*1000:
        raise ExecutionError("NEXT_CANDLE_NOT_STARTED")
    current,snapshot = decisions._calculate(db,contract,decision["signal_id"],now)
    if current["action"] != proposal["action"] or current["status"] != "CONDITIONAL_REVALIDATION_REQUIRED":
        raise ExecutionError("DECISION_CHANGED")
    if snapshot.ticker.source_time_ms < proposal["earliest_fill_candle"]*1000:
        raise ExecutionError("TICKER_BEFORE_DECISION")
    if any(t > now for t in (snapshot.ticker.source_time_ms,snapshot.source_time_ms,
                              snapshot.fetched_at_ms,snapshot.instrument["source_time_ms"])):
        raise ExecutionError("FUTURE_MARKET_CLOCK")
    if wallet["state"]["quantity"] != "0":
        last_mark = next((e for e in reversed(events) if e["kind"] == "mark"),None)
        evidence = db.execute("SELECT id FROM paper_mark_evidence WHERE event_id=?",(last_mark["event_id"],)).fetchone() if last_mark else None
        if not evidence:
            raise ExecutionError("VERIFIED_MARK_REQUIRED")
        mark = verify_mark(db,decisions.paper,evidence[0])
        if mark["ticker_source_time_ms"] != snapshot.ticker.source_time_ms or mark["price"] != decimal_text(snapshot.ticker.price):
            raise ExecutionError("MARK_PROVENANCE_MISMATCH")
    return decision,binding,wallet,current,snapshot


def preview_decision(path, identifier, max_age=90, clock=None):
    guard()
    service = DecisionService(path,max_age,clock)
    try:
        with service.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            service._time(db)
        with service.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = service._time(db)
            decision,_,wallet,current,_ = validate_for_execution(db,service,identifier,now)
            return {"status":"ELIGIBLE_FOR_VIRTUAL_REVIEW", "decision_id":identifier,
                    "wallet_sequence":wallet["sequence"], "action":decision["proposal"]["action"],
                    "proposal":current, "paper_fill_created":False,"live_execution_enabled":False}
    except ExecutionError:
        raise
    except (DecisionError,PaperError,PlannerError) as exc:
        raise ExecutionError(str(exc)) from None
    except sqlite3.Error:
        raise ExecutionError("PAPER_DATABASE_ERROR") from None
    except (ValueError,ArithmeticError):
        raise ExecutionError("PAPER_VALIDATION_INVALID") from None
