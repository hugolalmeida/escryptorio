"""Observações derivadas em uma transação somente leitura, sem coletor ou heartbeat."""
import hashlib
import json
import re
import time
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cryptolab.config import INTERVALS, SYMBOLS
from cryptolab.models import Snapshot
from cryptolab.monitor.service import digest
from cryptolab.paper.api import PaperEnvelope, _wallet, readonly
from cryptolab.paper.decisions import DecisionService
from cryptolab.paper.executor import verify_execution
from cryptolab.paper.marking import verify_mark
from cryptolab.paper.storage import PaperStore
from cryptolab.storage import canonical_dataset


class OperationalAlertDTO(BaseModel):
    id: str
    code: str
    severity: str
    component: str
    resource_id: str
    observed_at_ms: int
    source_time_ms: int | None
    first_seen_at_ms: None = None
    reason: str
    evidence: dict
    suggested_action: str
    status: str = "CURRENT_OBSERVATION"


class OperationalOverviewDTO(BaseModel):
    schema_version: int = 1
    observed_at_ms: int
    process_liveness: str = "UNKNOWN"
    financial_integrity: str
    collection: dict | None
    markets: list[dict]
    monitors: list[dict]
    wallets: list[dict]
    decisions: list[dict]
    alerts: list[OperationalAlertDTO]
    history_available: str = "LATEST_PERSISTED_STATE_ONLY"
    truncated: bool


def operations_router(path: Path, max_age: int) -> APIRouter:
    router = APIRouter(prefix="/api/v1/paper/operations", tags=["paper-operations-read-only"])
    paper, decisions = PaperStore(path), DecisionService(path)

    @router.get("/overview", response_model=PaperEnvelope)
    def overview():
        now = int(time.time() * 1000)
        alerts = []

        def alert(code, severity, component, resource, stamp, reason, evidence, action):
            identifier = digest({"version": 1, "code": code, "component": component, "resource_id": resource})[0]
            alerts.append(OperationalAlertDTO(id=identifier, code=code, severity=severity, component=component,
                resource_id=resource, observed_at_ms=now, source_time_ms=stamp, reason=reason,
                evidence=evidence, suggested_action=action))

        try:
            with readonly(path) as db:
                collection_row = db.execute("SELECT * FROM collection_status WHERE id=1").fetchone()
                collection = dict(collection_row) if collection_row else None
                if collection and collection["error_code"]:
                    code = collection["error_code"]
                    code = code if re.fullmatch(r"[A-Z0-9_]{1,64}", code) else "UNKNOWN_ERROR"
                    collection["error_code"] = code
                    alert("PUBLIC_COLLECTION_FAILED", "WARNING", "collection", "worker", collection["last_attempt_ms"],
                          "Última tentativa registrou erro.", {"error_code": code}, "Verifique a coleta pública e seus logs locais.")
                markets = []
                for symbol in SYMBOLS:
                    for interval in INTERVALS:
                        resource = symbol + ":" + interval
                        row = db.execute("SELECT payload FROM snapshots WHERE symbol=? AND interval=?", (symbol, interval)).fetchone()
                        status, source, fetched, dataset_id = "UNAVAILABLE", None, None, None
                        if row:
                            try:
                                snapshot = Snapshot.model_validate_json(row[0])
                                source, fetched, dataset_id = snapshot.source_time_ms, snapshot.fetched_at_ms, snapshot.dataset_id
                                data = db.execute("SELECT payload FROM datasets WHERE id=?", (dataset_id,)).fetchone()
                                inst = snapshot.instrument
                                lot = inst["lot_size_filter"]
                                step = INTERVALS[interval]
                                candles = snapshot.candles
                                if (snapshot.source != "Bybit" or snapshot.category != "spot" or snapshot.symbol != symbol or snapshot.interval != interval
                                    or snapshot.ticker.symbol != symbol or inst["symbol"] != symbol or inst["status"] != "Trading" or inst["quote_coin"] != "USDT"
                                    or not data or hashlib.sha256(data[0].encode()).hexdigest() != dataset_id
                                    or canonical_dataset(symbol, interval, snapshot.candles)[0] != dataset_id
                                    or not candles or any(c.time % step for c in candles)
                                    or any(b.time-a.time != step for a,b in zip(candles,candles[1:]))
                                    or any(c.closed != (c.time*1000+step*1000 <= source) for c in candles)
                                    or any(Decimal(str(lot[k])) <= 0 for k in ("basePrecision", "minOrderAmt", "maxMarketOrderQty"))
                                    or Decimal(str(inst["price_filter"]["tickSize"])) <= 0):
                                    raise ValueError()
                                stamps = (source, fetched, snapshot.ticker.source_time_ms, inst["source_time_ms"])
                                status = "DEGRADED" if any(t > now + 5000 for t in stamps) else "STALE" if any(now-t > max_age*1000 for t in stamps) else "HEALTHY"
                                if status == "DEGRADED":
                                    alert("MARKET_TIMESTAMP_FUTURE", "WARNING", "market", resource, source, "Relógio da fonte ou coleta no futuro.", {}, "Verifique os relógios e a coleta pública.")
                                elif status == "STALE":
                                    alert("MARKET_SNAPSHOT_STALE", "WARNING", "market", resource, source, "Snapshot ou metadados estão obsoletos.", {}, "Verifique o worker público e os horários das fontes.")
                            except (ValueError, KeyError, TypeError, ArithmeticError):
                                status, source, fetched, dataset_id = "DEGRADED", None, None, None
                                alert("MARKET_INTEGRITY_FAILED", "CRITICAL", "market", resource, None, "Snapshot ou instrumento inválido.", {}, "Inspecione os dados públicos persistidos.")
                        else:
                            alert("MARKET_SNAPSHOT_MISSING", "WARNING", "market", resource, None, "Snapshot ausente.", {}, "Verifique a coleta pública.")
                        markets.append({"symbol": symbol, "interval": interval, "status": status, "source_time_ms": source,
                            "fetched_at_ms": fetched, "age_ms": now-source if source is not None else None,
                            "stale_after_seconds": max_age, "dataset_id": dataset_id})
                monitors = []
                monitor_rows = db.execute("SELECT * FROM monitor_runtime ORDER BY bot_id,config_hash LIMIT 101").fetchall()
                for row in monitor_rows[:100]:
                    try:
                        definition = json.loads(row["definition"])
                        if digest(definition)[0] != row["config_hash"] or definition["config"]["bot_id"] != row["bot_id"]:
                            raise ValueError()
                        latest = db.execute("SELECT * FROM monitor_signals WHERE config_hash=? ORDER BY candle_time DESC LIMIT 1", (row["config_hash"],)).fetchone()
                        signal = json.loads(latest["payload"]) if latest else None
                        if (not latest and row["last_candle"] is not None) or (latest and (digest(signal) != (latest["id"], latest["payload"]) or digest(signal["definition"])[0] != row["config_hash"] or latest["bot_id"] != row["bot_id"] or signal["config_hash"] != row["config_hash"] or signal["candle_time"] != latest["candle_time"] or row["last_candle"] != latest["candle_time"])):
                            raise ValueError()
                        error = row["error_code"]
                        error = error if error and re.fullmatch(r"[A-Z0-9_]{1,64}", error) else None
                        monitors.append({"bot_id": row["bot_id"], "config_hash": row["config_hash"], "config": definition["config"],
                            "last_candle": row["last_candle"], "last_evaluation_ms": row["last_evaluation_ms"],
                            "state_observed": row["state"], "error_code": error, "process_liveness": "UNKNOWN",
                            "signal": {"id": latest["id"], **signal} if signal else None})
                        if error:
                            alert("MONITOR_RECORDED_ERROR", "WARNING", "monitor", row["config_hash"], row["last_evaluation_ms"], "Última avaliação registrou erro.", {"error_code": error}, "Inspecione o checkpoint e os dados públicos.")
                        if signal and signal.get("origin") == "current" and now >= signal["valid_until"]*1000:
                            alert("MONITOR_SIGNAL_EXPIRED", "INFO", "monitor", row["config_hash"], signal["valid_until"]*1000, "Sinal informativo expirado.", {"signal_id": latest["id"]}, "Consulte uma avaliação atual antes de qualquer análise.")
                    except (ValueError, KeyError, TypeError):
                        alert("MONITOR_INTEGRITY_FAILED", "CRITICAL", "monitor", row["config_hash"], None, "Checkpoint ou sinal inconsistente.", {}, "Inspecione o monitor local.")
                        monitors.append({"bot_id": row["bot_id"], "config_hash": row["config_hash"], "status": "DEGRADED", "process_liveness": "UNKNOWN"})
                alert("MONITOR_STATUS_UNKNOWN", "INFO", "monitor", "process", None, "Não há heartbeat contínuo verificável.", {}, "Consulte o processo local; não infira execução pelo último sinal.")
                wallets, failures = [], False
                wallet_rows = db.execute("SELECT id,bot_id FROM paper_wallets ORDER BY bot_id LIMIT 101").fetchall()
                for row in wallet_rows[:100]:
                    try:
                        wallet = _wallet(db, paper, row["id"], now, max_age)
                        _, events = paper._replay(db, row["id"])
                        for item in db.execute("SELECT id FROM paper_mark_evidence WHERE wallet_id=?", (row["id"],)).fetchall():
                            verify_mark(db, paper, item["id"])
                        for item in db.execute("SELECT id FROM paper_execution_evidence WHERE wallet_id=?", (row["id"],)).fetchall():
                            verify_execution(db, decisions, item["id"])
                        binding = db.execute("SELECT binding_id FROM paper_binding_active WHERE wallet_id=?", (row["id"],)).fetchone()
                        if binding: decisions._binding(db, binding[0])
                        fills = [e for e in events if e["kind"] == "fill"]
                        change = next((e for e in reversed(events) if e["kind"] == "state"), None)
                        wallets.append({"wallet_id": row["id"], "bot_id": row["bot_id"], "state": wallet["state"]["state"],
                            "binding_id": binding[0] if binding else None, "sequence": wallet["sequence"], "head_hash": wallet["head_hash"],
                            "integrity": "VERIFIED", "mark_status": wallet["mark_status"], "mark_source_time_ms": wallet["mark_source_time_ms"],
                            "fills": len(fills), "last_fill_time": fills[-1]["payload"]["input"]["event_time"] if fills else None,
                            "last_state_change": change["payload"]["input"]["event_time"] if change else None})
                        if wallet["state"]["state"] == "paused":
                            alert("PAPER_WALLET_PAUSED", "INFO", "wallet", row["id"], None, "Carteira pausada; pode ser intencional.", {}, "Revise o estado apenas se necessário.")
                        if Decimal(wallet["state"]["quantity"]) > 0 and wallet["mark_status"] != "FRESH":
                            alert("PAPER_MARK_STALE", "WARNING", "wallet", row["id"], wallet["mark_source_time_ms"], "Posição sem marcação fresca verificável.", {}, "Consulte a proveniência e o horário da marca.")
                    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
                        failures = True
                        wallets.append({"wallet_id": row["id"], "bot_id": row["bot_id"], "integrity": "FAILED"})
                        code = "PAPER_EVIDENCE_MISSING" if str(exc) == "EVIDENCE_MISSING" else "PAPER_LEDGER_INTEGRITY_FAILED"
                        alert(code, "CRITICAL", "wallet", row["id"], None, "Ledger ou evidência não pôde ser verificado.", {}, "Interrompa análises financeiras e inspecione a base local.")
                decision_rows = db.execute("SELECT id FROM paper_decisions ORDER BY candle_time DESC,id DESC LIMIT 101").fetchall()
                decision_items = []
                for row in decision_rows[:100]:
                    try:
                        item = decisions._decision(db, row["id"])
                        evidence = db.execute("SELECT id FROM paper_execution_evidence WHERE decision_id=?", (row["id"],)).fetchone()
                        if evidence: verify_execution(db, decisions, evidence[0])
                        temporal = "EXPIRED" if now >= item["proposal"]["expires_at"]*1000 else "CURRENT"
                        decision_items.append({"id": item["id"], "wallet_id": item["wallet_id"], "binding_id": item["binding_id"],
                            "signal_id": item["signal_id"], "action": item["proposal"]["action"], "state": item["state"],
                            "temporal_status": temporal, "expires_at": item["proposal"]["expires_at"],
                            "execution_id": evidence[0] if evidence else None, "reason": item["proposal"]["reason"]})
                        if item["state"] == "INVALIDATED" or temporal == "EXPIRED":
                            code = "DECISION_INVALIDATED" if item["state"] == "INVALIDATED" else "DECISION_EXPIRED"
                            alert(code, "INFO", "decision", item["id"], item["proposal"]["expires_at"]*1000,
                                  "Decisão histórica não está disponível para nova análise.", {}, "Consulte a decisão e seu estado auditável.")
                    except (ValueError, KeyError, TypeError, ArithmeticError):
                        failures = True
                        alert("DECISION_INTEGRITY_FAILED", "CRITICAL", "decision", row["id"], None, "Decisão ou evidência inconsistente.", {}, "Inspecione a base local.")
                truncated = any(len(rows) > 100 for rows in (wallet_rows, monitor_rows, decision_rows))
                result = OperationalOverviewDTO(observed_at_ms=now, financial_integrity="DEGRADED" if failures else "PARTIAL_VERIFIED" if wallets or decision_items else "UNKNOWN",
                    collection=collection, markets=markets, monitors=monitors, wallets=wallets, decisions=decision_items,
                    alerts=alerts, truncated=truncated)
                return PaperEnvelope(observed_at_ms=now, data=result.model_dump())
        except (ValueError, OSError, KeyError, TypeError, ArithmeticError):
            raise HTTPException(503, "Observabilidade local indisponível.") from None
        except Exception:
            raise HTTPException(503, "Observabilidade local indisponível.") from None
    return router
