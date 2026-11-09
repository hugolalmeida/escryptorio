"""Simulação manual e local, exclusivamente virtual, sem dependências de rede."""
import json
import re
import sqlite3
from decimal import Decimal as D, ROUND_UP, localcontext

from cryptolab.config import INTERVALS
from cryptolab.history.models import decimal_text
from cryptolab.models import Snapshot
from cryptolab.monitor.models import MonitorConfig
from cryptolab.monitor.service import digest, validated
from cryptolab.paper.decisions import DecisionError, DecisionService
from cryptolab.paper.executor_models import (ExecutionCheckpoint, VirtualExecutionRequest,
    VirtualFillEvidence, VirtualExecutionResult)
from cryptolab.paper.ledger import LEDGER_CONTEXT
from cryptolab.paper.marking import ExecutionError, VERSION, guard, validate_for_execution, verify_mark
from cryptolab.paper.models import FillRecord
from cryptolab.paper.planner import PlannerError, _ceil, _floor
from cryptolab.paper.storage import PaperError
from cryptolab.storage import canonical_dataset


def _round_fee(value):
    return value.quantize(D("0.000000000000000001"), rounding=ROUND_UP)


def verify_execution(db, service, identifier):
    row = db.execute("SELECT * FROM paper_execution_evidence WHERE id=?", (identifier,)).fetchone()
    if not row:
        raise ExecutionError("EXECUTION_NOT_FOUND")
    try:
        body = json.loads(row["payload"])
        evidence = VirtualFillEvidence.model_validate(body)
        if (digest(body) != (row["id"],row["payload"]) or evidence.executor_version != VERSION
            or any(body[k] != row[k] for k in ("decision_id","wallet_id","binding_id","signal_id","candle_time","action","idempotency_key","event_id"))):
            raise ValueError()
        decision = service._decision(db,evidence.decision_id)
        binding = service._binding(db,evidence.binding_id)
        config = MonitorConfig.model_validate(binding["monitor_definition"]["config"])
        p = evidence.proposal
        snapshot = Snapshot.model_validate(evidence.snapshot)
        signal_row = db.execute("SELECT payload FROM monitor_signals WHERE id=?",(evidence.signal_id,)).fetchone()
        signal = json.loads(signal_row[0]) if signal_row else None
        if (decision["wallet_id"] != evidence.wallet_id or decision["binding_id"] != evidence.binding_id
            or decision["signal_id"] != evidence.signal_id or decision["candle_time"] != evidence.candle_time
            or decision["proposal"]["action"] != evidence.action or p["action"] != evidence.action
            or decision["proposal"]["wallet_sequence"] != evidence.before.wallet_sequence
            or decision["proposal"]["wallet_head_hash"] != evidence.before.wallet_head_hash
            or p["signal_id"] != evidence.signal_id or p["wallet_id"] != evidence.wallet_id
            or not signal or signal.get("schema_version") != 2 or signal.get("origin") != "current"
            or signal.get("eligible_for_future_paper_analysis") is not True
            or signal.get("mode") != "informational_only" or signal.get("position_checked") is not False
            or p["monitor_config_hash"] != binding["monitor_config_hash"]
            or p["binding_hash"] != digest(binding["binding"])[0] or p["risk"] != binding["binding"]["risk"]
            or p["wallet_sequence"] != evidence.before.wallet_sequence or p["wallet_head_hash"] != evidence.before.wallet_head_hash
            or p["validation_hash"] != digest({k:v for k,v in p.items() if k != "validation_hash"})[0]
            or p["snapshot_hash"] != evidence.snapshot_hash or digest(evidence.snapshot)[0] != evidence.snapshot_hash
            or p["instrument_hash"] != evidence.instrument_hash or digest(snapshot.instrument)[0] != evidence.instrument_hash
            or p["reference_price"] != decimal_text(snapshot.ticker.price)
            or evidence.symbol != snapshot.symbol or evidence.interval != snapshot.interval
            or p["symbol"] != evidence.symbol or p["interval"] != evidence.interval
            or evidence.ticker_source_time_ms != snapshot.ticker.source_time_ms or evidence.fetched_at_ms != snapshot.fetched_at_ms
            or p["ticker_source_time_ms"] != snapshot.ticker.source_time_ms
            or snapshot.instrument["symbol"] != snapshot.symbol or snapshot.instrument["status"] != "Trading"
            or snapshot.instrument["quote_coin"] != "USDT" or snapshot.ticker.symbol != snapshot.symbol
            or canonical_dataset(snapshot.symbol,snapshot.interval,snapshot.candles)[0] != snapshot.dataset_id
            or snapshot.dataset_id != decision["proposal"]["dataset_id"]
            or evidence.fill_candle_time != decision["proposal"]["earliest_fill_candle"]
            or not evidence.fill_candle_time*1000 <= evidence.execution_time_ms < decision["proposal"]["expires_at"]*1000
            or snapshot.ticker.source_time_ms < evidence.fill_candle_time*1000
            or any(t > evidence.execution_time_ms or evidence.execution_time_ms-t > evidence.max_age_seconds*1000
                   for t in (snapshot.ticker.source_time_ms,snapshot.source_time_ms,snapshot.fetched_at_ms,snapshot.instrument["source_time_ms"]))):
            raise ValueError()
        validated(snapshot,config,evidence.execution_time_ms,evidence.max_age_seconds)
        if (not any(e["event_hash"] == evidence.decision_event_hash and e["kind"] == "RECORDED"
                    and e["at_ms"] <= evidence.execution_time_ms for e in decision["events"])
            or not any(e["event_hash"] == evidence.binding_event_hash and e["kind"] == "ACTIVE"
                       and e["at_ms"] <= evidence.execution_time_ms for e in binding["events"])):
            raise ValueError()
        _, events = service.paper._replay(db,evidence.wallet_id)
        event = next(e for e in events if e["event_id"] == evidence.event_id)
        entry = event["payload"]["input"]
        if (event["kind"] != "fill" or event["event_hash"] != evidence.event_hash
            or event["sequence"] != evidence.after.wallet_sequence or event["previous_hash"] != evidence.before.wallet_head_hash
            or event["idempotency_key"] != "exec-"+digest({"wallet_id":evidence.wallet_id,"key":evidence.idempotency_key})[0]
            or evidence.after.wallet_sequence != evidence.before.wallet_sequence+1
            or evidence.after.wallet_head_hash != event["event_hash"]
            or entry["side"] != evidence.action.lower() or entry["quantity"] != p["planned_quantity"]
            or entry["price"] != p["estimated_price"] or entry["reference_price"] != p["reference_price"]
            or entry["candle_time"] != evidence.fill_candle_time or entry["event_time"] != evidence.execution_time_ms//1000):
            raise ValueError()
        if (evidence.action == "SELL" and not evidence.mark_id) or (evidence.action == "BUY" and D(event["payload"]["before"]["quantity"]) != 0):
            raise ValueError()
        if evidence.action == "BUY" and evidence.protection != {"stop":p["planned_stop"],"target":p["planned_target"],
                "status":"HYPOTHETICAL_ONLY","automatic_monitoring":False}:
            raise ValueError()
        with localcontext(LEDGER_CONTEXT):
            quantity, price, reference = D(entry["quantity"]), D(entry["price"]), D(entry["reference_price"])
            slip, rate = D(p["risk"]["costs"]["slippage_rate"]), D(p["risk"]["costs"]["fee_rate"])
            lot = snapshot.instrument["lot_size_filter"]
            tick, step = D(snapshot.instrument["price_filter"]["tickSize"]), D(lot["basePrecision"])
            expected_price = _ceil(reference*(D(1)+slip),tick) if evidence.action == "BUY" else _floor(reference*(D(1)-slip),tick)
            if (D(entry["fee"]) != _round_fee(quantity*price*rate) or price != expected_price
                or quantity != _floor(quantity,step) or quantity > D(lot["maxMarketOrderQty"])
                or quantity*price < D(lot["minOrderAmt"])
                or (lot.get("maxMarketOrderAmt") and quantity*price > D(lot["maxMarketOrderAmt"]))
                or D(p["estimated_slippage"]) != abs(price-reference)*quantity):
                raise ValueError()
            if evidence.action == "BUY":
                cash = D(event["payload"]["before"]["cash"])
                post_equity = cash-quantity*price-D(entry["fee"])+quantity*reference
                stop = _floor(price*(D(1)-config.parameters.stop_fraction),tick)
                target = _ceil(price*(D(1)+config.parameters.target_fraction),tick)
                exit_price = _floor(stop*(D(1)-slip),tick)
                risk = quantity*(price-exit_price)+D(entry["fee"])+_round_fee(quantity*exit_price*rate)
                if (D(p["planned_stop"]) != stop or D(p["planned_target"]) != target or stop <= 0
                    or post_equity <= 0 or quantity*reference > post_equity*D(p["risk"]["exposure_fraction"])
                    or risk > cash*D(p["risk"]["risk_fraction"])):
                    raise ValueError()
        if evidence.mark_id:
            mark = verify_mark(db,service.paper,evidence.mark_id)
            if (mark["wallet_id"] != evidence.wallet_id or mark["ticker_source_time_ms"] != snapshot.ticker.source_time_ms
                or mark["price"] != decimal_text(snapshot.ticker.price)
                or mark["ledger_event"]["sequence"] > evidence.before.wallet_sequence):
                raise ValueError()
        if evidence.action == "SELL" and evidence.protection:
            remaining = event["payload"]["after"]["quantity"]
            if (evidence.protection.get("remaining_quantity") != remaining
                or evidence.protection.get("automatic_monitoring") is not False):
                raise ValueError()
            source_id = evidence.protection.get("source_execution")
            if source_id:
                source_row = db.execute("SELECT action FROM paper_execution_evidence WHERE id=?",(source_id,)).fetchone()
                if not source_row or source_row[0] != "BUY" or source_id == identifier:
                    raise ValueError()
                source = verify_execution(db,service,source_id)
                if (source["ledger_event"]["sequence"] >= event["sequence"] or source["evidence"]["wallet_id"] != evidence.wallet_id
                    or source["evidence"]["protection"] != evidence.protection.get("previous_protection")):
                    raise ValueError()
        return VirtualExecutionResult(execution_id=identifier,receipt_mode="RECOVER_VIRTUAL_FILL",
            evidence=body,ledger_event=event).model_dump(mode="json")
    except ExecutionError:
        raise
    except (KeyError,ValueError,TypeError,ArithmeticError,StopIteration,DecisionError,PaperError):
        raise ExecutionError("EXECUTION_INTEGRITY_ERROR") from None


class PaperExecutor:
    def __init__(self, path, max_age=90, clock=None):
        self.service = DecisionService(path,max_age,clock)
        self.max_age = max_age

    def execute(self, request: VirtualExecutionRequest, *, paper: bool = False) -> dict:
        guard(True)
        if paper is not True:
            raise ExecutionError("EXPLICIT_PAPER_REQUIRED")
        request = VirtualExecutionRequest.model_validate(request.model_dump() if isinstance(request,VirtualExecutionRequest) else request)
        try:
            with self.service.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                self.service._time(db)
            with self.service.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                now = self.service._time(db)
                decision = self.service._decision(db,request.decision_id)
                wallet_id = decision["wallet_id"]
                rows = db.execute("SELECT id FROM paper_execution_evidence WHERE decision_id=? OR (wallet_id=? AND idempotency_key=?)",
                                  (request.decision_id,wallet_id,request.idempotency_key)).fetchall()
                if len(rows) > 1:
                    raise ExecutionError("EXECUTION_CONFLICT")
                if rows:
                    receipt = verify_execution(db,self.service,rows[0][0])
                    if (receipt["evidence"]["decision_id"] != request.decision_id
                        or receipt["evidence"]["idempotency_key"] != request.idempotency_key):
                        raise ExecutionError("EXECUTION_CONFLICT")
                    return receipt
                decision,binding,wallet,proposal,snapshot = validate_for_execution(db,self.service,request.decision_id,now)
                with localcontext(LEDGER_CONTEXT):
                    quantity, price, reference = (D(proposal[k]) for k in ("planned_quantity","estimated_price","reference_price"))
                    fee = _round_fee(quantity*price*D(proposal["risk"]["costs"]["fee_rate"]))
                    cash = D(wallet["state"]["cash"])
                    if proposal["action"] == "BUY":
                        if quantity*price+fee > cash:
                            raise ExecutionError("INSUFFICIENT_BALANCE")
                        post_equity = cash-quantity*price-fee+quantity*reference
                        if post_equity <= 0 or quantity*reference > post_equity*D(proposal["risk"]["exposure_fraction"]):
                            raise ExecutionError("EXPOSURE_LIMIT_EXCEEDED")
                        slip = D(proposal["risk"]["costs"]["slippage_rate"])
                        tick = D(snapshot.instrument["price_filter"]["tickSize"])
                        stop_exit = _floor(D(proposal["planned_stop"])*(D(1)-slip),tick)
                        exit_fee = _round_fee(quantity*stop_exit*D(proposal["risk"]["costs"]["fee_rate"]))
                        risk = quantity*(price-stop_exit)+fee+exit_fee
                        if risk > cash*D(proposal["risk"]["risk_fraction"]):
                            raise ExecutionError("RISK_LIMIT_AFTER_ROUNDING")
                    else:
                        if quantity > D(wallet["state"]["quantity"]):
                            raise ExecutionError("SELL_EXCEEDS_POSITION")
                        if fee > quantity*price:
                            raise ExecutionError("SELL_FEE_EXCEEDS_PROCEEDS")
                    candle = proposal["earliest_fill_candle"]
                    fill = FillRecord(side=proposal["action"].lower(),quantity=quantity,price=price,fee=fee,
                                      reference_price=reference,candle_time=candle,event_time=now//1000)
                    key = "exec-"+digest({"wallet_id":wallet_id,"key":request.idempotency_key})[0]
                    if db.execute("SELECT 1 FROM paper_events WHERE wallet_id=? AND idempotency_key=?",(wallet_id,key)).fetchone():
                        raise ExecutionError("EXECUTION_LEDGER_KEY_CONFLICT")
                    mark_id = None
                    if D(wallet["state"]["quantity"]) > 0:
                        _, events = self.service.paper._replay(db,wallet_id)
                        last_mark = next(e for e in reversed(events) if e["kind"] == "mark")
                        mark_id = db.execute("SELECT id FROM paper_mark_evidence WHERE event_id=?",(last_mark["event_id"],)).fetchone()[0]
                    event = self.service.paper.append_in_transaction(db,wallet_id,key,fill)
                    if proposal["action"] == "BUY":
                        protection = {"stop":proposal["planned_stop"],"target":proposal["planned_target"],
                                      "status":"HYPOTHETICAL_ONLY","automatic_monitoring":False}
                    else:
                        remaining = event["payload"]["after"]["quantity"]
                        previous_protection = None
                        source_execution = None
                        if D(remaining) > 0:
                            last_buy = next((e for e in reversed(events) if e["kind"] == "fill"
                                             and e["payload"]["input"]["side"] == "buy"),None)
                            source = db.execute("SELECT id FROM paper_execution_evidence WHERE event_id=?",(last_buy["event_id"],)).fetchone() if last_buy else None
                            if source:
                                previous = verify_execution(db,self.service,source[0])
                                source_execution = source[0]
                                previous_protection = previous["evidence"]["protection"]
                        protection = {"remaining_quantity":remaining,"status":"POSITION_REDUCED" if D(remaining)>0 else "POSITION_CLOSED",
                                      "source_execution":source_execution,"previous_protection":previous_protection,
                                      "automatic_monitoring":False}
                    body = VirtualFillEvidence(executor_version=VERSION,decision_id=request.decision_id,wallet_id=wallet_id,
                        binding_id=decision["binding_id"],signal_id=decision["signal_id"],idempotency_key=request.idempotency_key,
                        symbol=snapshot.symbol,interval=snapshot.interval,action=proposal["action"],candle_time=decision["candle_time"],
                        fill_candle_time=candle,execution_time_ms=now,ticker_source_time_ms=snapshot.ticker.source_time_ms,
                        fetched_at_ms=snapshot.fetched_at_ms,
                        max_age_seconds=self.max_age,snapshot_hash=proposal["snapshot_hash"],instrument_hash=proposal["instrument_hash"],
                        mark_id=mark_id,decision_event_hash=decision["events"][-1]["event_hash"],
                        binding_event_hash=binding["events"][-1]["event_hash"],event_id=event["event_id"],event_hash=event["event_hash"],
                        before=ExecutionCheckpoint(wallet_sequence=wallet["sequence"],wallet_head_hash=wallet["head_hash"]),
                        after=ExecutionCheckpoint(wallet_sequence=event["sequence"],wallet_head_hash=event["event_hash"]),
                        proposal=proposal,snapshot=snapshot.model_dump(mode="json"),protection=protection).model_dump(mode="json")
                identifier,payload = digest(body)
                db.execute("INSERT INTO paper_execution_evidence VALUES (?,?,?,?,?,?,?,?,?,?)",(identifier,request.decision_id,
                    wallet_id,decision["binding_id"],decision["signal_id"],decision["candle_time"],proposal["action"],
                    request.idempotency_key,event["event_id"],payload))
                # Fail closed if freshness or decision validity changed while computing.
                check = self.service._time(db)
                if check >= decision["proposal"]["expires_at"]*1000 or check-now > self.max_age*1000:
                    raise ExecutionError("DECISION_EXPIRED_DURING_EXECUTION")
                validated(snapshot,MonitorConfig.model_validate(binding["monitor_definition"]["config"]),check,self.max_age)
                if any(check-t > self.max_age*1000 for t in (snapshot.ticker.source_time_ms,snapshot.instrument["source_time_ms"])):
                    raise ExecutionError("STALE_MARKET_DURING_EXECUTION")
                receipt = verify_execution(db,self.service,identifier)
                final = self.service._time(db)
                if final >= decision["proposal"]["expires_at"]*1000:
                    raise ExecutionError("DECISION_EXPIRED_DURING_EXECUTION")
                validated(snapshot,MonitorConfig.model_validate(binding["monitor_definition"]["config"]),final,self.max_age)
                if any(final-t > self.max_age*1000 for t in (snapshot.ticker.source_time_ms,snapshot.instrument["source_time_ms"])):
                    raise ExecutionError("STALE_MARKET_DURING_EXECUTION")
                guard(True)
                receipt["receipt_mode"]="NEW_VIRTUAL_FILL"
                return receipt
        except ExecutionError:
            raise
        except (DecisionError,PaperError,PlannerError) as exc:
            raise ExecutionError(str(exc)) from None
        except sqlite3.IntegrityError:
            raise ExecutionError("EXECUTION_CONFLICT") from None
        except sqlite3.Error:
            raise ExecutionError("PAPER_DATABASE_ERROR") from None
        except (ValueError,ArithmeticError):
            raise ExecutionError("EXECUTION_INPUT_INVALID") from None

    def receipt(self, identifier: str) -> dict:
        guard()
        with self.service.store.connect() as db:
            db.execute("BEGIN")
            return verify_execution(db,self.service,identifier)

    def history(self, wallet_id: str) -> list[dict]:
        guard()
        with self.service.store.connect() as db:
            db.execute("BEGIN")
            return [verify_execution(db,self.service,r[0]) for r in db.execute(
                "SELECT id FROM paper_execution_evidence WHERE wallet_id=? ORDER BY rowid",(wallet_id,)).fetchall()]

    def verify_integrity(self) -> dict:
        guard()
        try:
            with self.service.store.connect() as db:
                db.execute("BEGIN")
                if db.execute("PRAGMA foreign_key_check").fetchone():
                    raise ExecutionError("REFERENTIAL_INTEGRITY_ERROR")
                wallets = db.execute("SELECT id FROM paper_wallets").fetchall()
                bindings = [self.service._binding(db,r[0]) for r in db.execute("SELECT id FROM paper_bindings").fetchall()]
                decisions = [self.service._decision(db,r[0]) for r in db.execute("SELECT id FROM paper_decisions").fetchall()]
                for row in wallets:
                    self.service.paper._replay(db,row[0])
                if (db.execute("SELECT COUNT(*) FROM paper_binding_heads").fetchone()[0] != len(bindings)
                    or db.execute("SELECT COUNT(*) FROM paper_decision_heads").fetchone()[0] != len(decisions)
                    or db.execute("SELECT COUNT(*) FROM paper_binding_active").fetchone()[0] != sum(b["state"] == "ACTIVE" for b in bindings)):
                    raise ExecutionError("PROJECTION_INTEGRITY_ERROR")
                checkpoint = db.execute("SELECT high_water_ms FROM paper_decision_clock WHERE id=1").fetchone()
                latest = max((event["at_ms"] for item in bindings+decisions for event in item["events"]),default=0)
                if not checkpoint or checkpoint[0] < latest:
                    raise ExecutionError("CLOCK_CHECKPOINT_INTEGRITY_ERROR")
                marks = db.execute("SELECT id FROM paper_mark_evidence").fetchall()
                executions = db.execute("SELECT id FROM paper_execution_evidence").fetchall()
                for row in marks:
                    verify_mark(db,self.service.paper,row[0])
                for row in executions:
                    verify_execution(db,self.service,row[0])
                for event in db.execute("SELECT event_id,idempotency_key FROM paper_events WHERE kind IN ('mark','fill')"):
                    key = event["idempotency_key"]
                    if re.fullmatch(r"exec-[a-f0-9]{64}",key):
                        if not db.execute("SELECT 1 FROM paper_execution_evidence WHERE event_id=?",(event["event_id"],)).fetchone():
                            raise ExecutionError("EXECUTION_EVIDENCE_MISSING")
                    if re.fullmatch(r"mark-[a-f0-9]{64}",key):
                        if not db.execute("SELECT 1 FROM paper_mark_evidence WHERE event_id=?",(event["event_id"],)).fetchone():
                            raise ExecutionError("MARK_EVIDENCE_MISSING")
                return {"valid":True,"wallets":len(wallets),"bindings":len(bindings),"decisions":len(decisions),
                        "marks":len(marks),"executions":len(executions),"live_execution_enabled":False}
        except ExecutionError:
            raise
        except (DecisionError,PaperError) as exc:
            raise ExecutionError(str(exc)) from None
        except sqlite3.Error:
            raise ExecutionError("PAPER_DATABASE_ERROR") from None
