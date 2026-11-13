"""Projeções locais paper: somente SQLite read-only, sem atualização de relógio."""
import json
import hashlib
import re
import sqlite3
import time
from contextlib import contextmanager
from decimal import Decimal, localcontext
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from cryptolab.history.models import decimal_text
from cryptolab.monitor.service import digest
from cryptolab.models import Snapshot
from cryptolab.paper.decisions import DecisionService
from cryptolab.paper.executor import verify_execution
from cryptolab.paper.ledger import LEDGER_CONTEXT
from cryptolab.paper.marking import verify_mark
from cryptolab.paper.storage import PaperStore
from cryptolab.storage import canonical_dataset


class PaperEnvelope(BaseModel):
    schema_version: int = 1
    observed_at_ms: int
    data: dict | list


class PaperStateDTO(BaseModel):
    model_config = ConfigDict(extra="allow")
    cash: str
    quantity: str
    acquisition_cost: str
    realized_pnl: str
    total_fees: str
    state: str


class PaperWalletDTO(BaseModel):
    model_config = ConfigDict(extra="allow")
    wallet_id: str
    wallet_hash: str
    head_hash: str
    sequence: int
    state: PaperStateDTO
    spec: dict
    equity: str | None
    unrealized_pnl: str | None
    total_pnl: str | None
    position_value: str | None
    mark_status: str


class PaperOverviewDTO(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: dict
    wallets: list[PaperWalletDTO]


class PaperOverviewEnvelope(BaseModel):
    schema_version: int = 1
    observed_at_ms: int
    data: PaperOverviewDTO


class PaperWalletEnvelope(BaseModel):
    schema_version: int = 1
    observed_at_ms: int
    data: PaperWalletDTO


@contextmanager
def readonly(path: Path):
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN")
        migrations = {r[0] for r in db.execute("SELECT version FROM schema_migrations")}
        if not {"005_paper_ledger", "008_paper_decisions", "009_paper_execution"} <= migrations:
            raise ValueError("MIGRATIONS_REQUIRED")
        yield db
    finally:
        db.close()


def _wallet(db, paper, wid, now, max_age):
    view, events = paper._replay(db, wid)
    state, spec = view["state"], view["spec"]
    # Reserved keys promise a sidecar; an orphan cannot be labelled a valid ledger.
    for event in events:
        key = event["idempotency_key"]
        table = "paper_execution_evidence" if re.fullmatch(r"exec-[a-f0-9]{64}", key) else "paper_mark_evidence" if re.fullmatch(r"mark-[a-f0-9]{64}", key) else None
        if table and not db.execute("SELECT 1 FROM " + table + " WHERE event_id=?", (event["event_id"],)).fetchone():
            raise ValueError("EVIDENCE_MISSING")
    qty = Decimal(state["quantity"])
    mark = None
    # Only the latest ledger mark can describe the current position.
    last_mark = next((e for e in reversed(events) if e["kind"] == "mark"), None)
    if last_mark:
        row = db.execute("SELECT id FROM paper_mark_evidence WHERE event_id=?", (last_mark["event_id"],)).fetchone()
        if row:
            mark = verify_mark(db, paper, row[0])
        elif last_mark["idempotency_key"].startswith("mark-"):
            raise ValueError("MARK_EVIDENCE_MISSING")
    stamp = mark["ticker_source_time_ms"] if mark else None
    last_fill = next((e for e in reversed(events) if e["kind"] == "fill"), None)
    fresh = bool(mark and (not last_fill or last_mark["sequence"] > last_fill["sequence"])
                 and 0 <= now - stamp <= max_age * 1000)
    with localcontext(LEDGER_CONTEXT):
        cash, cost, realized = map(Decimal, (state["cash"], state["acquisition_cost"], state["realized_pnl"]))
        value = qty * Decimal(mark["price"]) if qty and fresh else (Decimal(0) if not qty else None)
        unrealized = value - cost if value is not None else None
        equity = cash + value if value is not None else None
        total = realized + unrealized if unrealized is not None else None
        avg = cost / qty if qty else None
        exposure = value / equity if value is not None and equity and qty else (Decimal(0) if not qty else None)
        def txt(v): return decimal_text(v) if v is not None else None
        return {**view, "quote": "USDT", "integrity": "VERIFIED", "average_cost": txt(avg),
                "mark_status": "FRESH" if fresh else "STALE" if mark else "UNAVAILABLE",
                "mark_price": mark["price"] if mark else None, "mark_source_time_ms": stamp,
                "mark_id": mark["id"] if mark else None, "position_value": txt(value), "exposure": txt(exposure),
                "equity": txt(equity), "unrealized_pnl": txt(unrealized), "total_pnl": txt(total),
                "last_event_time": state["last_event_time"]}


def paper_router(path: Path, max_age: int) -> APIRouter:
    router = APIRouter(prefix="/api/v1/paper", tags=["paper-read-only"])
    paper = PaperStore(path)
    decisions = DecisionService(path)

    def response(fn):
        try:
            now = int(time.time() * 1000)
            with readonly(path) as db:
                return PaperEnvelope(observed_at_ms=now, data=fn(db, now)).model_dump()
        except HTTPException:
            raise
        except (ValueError, sqlite3.Error, OSError, KeyError, TypeError, ArithmeticError):
            raise HTTPException(503, "Dados paper indisponíveis ou falha de integridade.") from None

    def wallet_id(value):
        if not re.fullmatch(r"[a-f0-9]{32}", value):
            raise HTTPException(422, "Identificador de carteira inválido.")
        return value

    @router.get("/overview", response_model=PaperOverviewEnvelope)
    def overview():
        def read(db, now):
            wallets = [_wallet(db, paper, r[0], now, max_age) for r in db.execute("SELECT id FROM paper_wallets ORDER BY bot_id")]
            with localcontext(LEDGER_CONTEXT):
                def total(field):
                    values = [w.get(field) for w in wallets]
                    return decimal_text(sum((Decimal(v) for v in values if v is not None), Decimal(0))) if all(v is not None for v in values) else None
                def state_total(field):
                    return decimal_text(sum((Decimal(w["state"][field]) for w in wallets), Decimal(0)))
                summary = {"initial_capital": decimal_text(sum((Decimal(w["spec"]["initial_capital"]) for w in wallets), Decimal(0))),
                           "cash": state_total("cash"), "realized_pnl": state_total("realized_pnl"),
                           "equity": total("equity"), "unrealized_pnl": total("unrealized_pnl"), "total_pnl": total("total_pnl"),
                           "position_value": total("position_value"), "quote": "USDT", "wallets": len(wallets),
                           "positions": sum(Decimal(w["state"]["quantity"]) > 0 for w in wallets),
                           "fills": db.execute("SELECT COUNT(*) FROM paper_events WHERE kind='fill'").fetchone()[0],
                           "decisions": db.execute("SELECT COUNT(*) FROM paper_decisions").fetchone()[0],
                           "integrity": "WALLETS_VERIFIED"}
            status = db.execute("SELECT * FROM collection_status WHERE id=1").fetchone()
            markets = []
            for symbol in ("BTCUSDT", "ETHUSDT"):
                row = db.execute("SELECT payload FROM snapshots WHERE symbol=? AND interval='60'", (symbol,)).fetchone()
                snap = Snapshot.model_validate_json(row[0]) if row else None
                if snap:
                    dataset = db.execute("SELECT payload FROM datasets WHERE id=?", (snap.dataset_id,)).fetchone()
                    if (snap.symbol != symbol or snap.interval != '60' or snap.source != 'Bybit' or snap.category != 'spot'
                        or canonical_dataset(symbol, '60', snap.candles)[0] != snap.dataset_id or not dataset
                        or hashlib.sha256(dataset[0].encode()).hexdigest() != snap.dataset_id):
                        raise ValueError("SNAPSHOT_INTEGRITY_ERROR")
                stamp = snap.source_time_ms if snap else None
                markets.append({"symbol": symbol, "source_time_ms": stamp,
                                "status": "UNAVAILABLE" if stamp is None else "HEALTHY" if 0 <= now-stamp <= max_age*1000 else "STALE"})
            return {"summary": summary, "wallets": wallets, "markets": markets,
                    "collection": dict(status) if status else None, "monitor_status": "UNKNOWN"}
        return response(read)

    @router.get("/wallets/{wid}", response_model=PaperWalletEnvelope)
    def wallet(wid: str):
        wallet_id(wid)
        def read(db, now):
            if not db.execute("SELECT 1 FROM paper_wallets WHERE id=?", (wid,)).fetchone(): raise HTTPException(404, "Carteira não encontrada.")
            item = _wallet(db, paper, wid, now, max_age)
            active = db.execute("SELECT binding_id FROM paper_binding_active WHERE wallet_id=?", (wid,)).fetchone()
            item["binding"] = decisions._binding(db, active[0]) if active else None
            return item
        return response(read)

    @router.get("/wallets/{wid}/events", response_model=PaperEnvelope)
    def events(wid: str, offset: int = Query(0, ge=0, le=1000000), limit: int = Query(20, ge=1, le=100)):
        wallet_id(wid)
        def read(db, now):
            _, rows = paper._replay(db, wid)
            ordered = list(reversed(rows))
            return {"items": ordered[offset:offset+limit], "total": len(rows), "offset": offset, "limit": limit}
        return response(read)

    @router.get("/wallets/{wid}/fills", response_model=PaperEnvelope)
    def fills(wid: str, offset: int = Query(0, ge=0, le=1000000), limit: int = Query(20, ge=1, le=100)):
        wallet_id(wid)
        def read(db, now):
            _, events = paper._replay(db, wid)
            fills = [e for e in reversed(events) if e["kind"] == "fill"]
            page = []
            for event in fills[offset:offset+limit]:
                sidecar = db.execute("SELECT id FROM paper_execution_evidence WHERE event_id=?", (event["event_id"],)).fetchone()
                if sidecar:
                    evidence = verify_execution(db, decisions, sidecar[0])
                    page.append({"event": event, "provenance": "VERIFIED", "execution_id": sidecar[0],
                                 "decision_id": evidence["evidence"]["decision_id"], "slippage": evidence["evidence"]["proposal"]["estimated_slippage"]})
                elif event["idempotency_key"].startswith("exec-"):
                    raise ValueError("EXECUTION_EVIDENCE_MISSING")
                else:
                    page.append({"event": event, "provenance": "LEGACY_UNVERIFIED", "execution_id": None, "decision_id": None, "slippage": None})
            return {"items": page, "total": len(fills), "offset": offset, "limit": limit}
        return response(read)

    @router.get("/wallets/{wid}/equity", response_model=PaperEnvelope)
    def equity(wid: str):
        wallet_id(wid)
        def read(db, now):
            _, events = paper._replay(db, wid)
            points = []
            for event in events:
                state = event["payload"]["after"]
                if event["kind"] == "genesis" or (event["kind"] == "fill" and Decimal(state["quantity"]) == 0):
                    value = state["cash"]
                elif event["kind"] == "mark":
                    evidence = db.execute("SELECT id FROM paper_mark_evidence WHERE event_id=?", (event["event_id"],)).fetchone()
                    if not evidence:
                        if event["idempotency_key"].startswith("mark-"): raise ValueError("MARK_EVIDENCE_MISSING")
                        continue
                    verify_mark(db, paper, evidence[0])
                    value = state["equity"]
                else:
                    continue
                points.append({"time": state["last_event_time"], "value": value, "kind": event["kind"], "sequence": event["sequence"]})
            return {"items": points[-500:], "truncated": len(points) > 500, "policy": "VERIFIED_OBSERVATIONS_ONLY"}
        return response(read)

    @router.get("/signals", response_model=PaperEnvelope)
    def signals(limit: int = Query(20, ge=1, le=100)):
        def read(db, now):
            items = []
            for row in db.execute("SELECT * FROM monitor_signals ORDER BY candle_time DESC,id DESC LIMIT ?", (limit,)):
                value = json.loads(row["payload"])
                if (digest(value) != (row["id"], row["payload"]) or digest(value["definition"])[0] != row["config_hash"]
                    or value["config_hash"] != row["config_hash"] or value["candle_time"] != row["candle_time"]
                    or value["definition"]["config"]["bot_id"] != row["bot_id"]):
                    raise ValueError("SIGNAL_INTEGRITY_ERROR")
                status = "HISTORICAL" if value.get("origin") == "historical_recovered" else "UNKNOWN" if value.get("origin") != "current" else "EXPIRED" if now >= value["valid_until"]*1000 else "CURRENT"
                items.append({"id": row["id"], **value, "temporal_status": status})
            return items
        return response(read)

    @router.get("/decisions", response_model=PaperEnvelope)
    def decision_list(limit: int = Query(20, ge=1, le=100)):
        def read(db, now):
            items = []
            for row in db.execute("SELECT id FROM paper_decisions ORDER BY candle_time DESC,id DESC LIMIT ?", (limit,)).fetchall():
                item = decisions._decision(db, row[0])
                filled = db.execute("SELECT id FROM paper_execution_evidence WHERE decision_id=?", (row[0],)).fetchone()
                if filled: verify_execution(db, decisions, filled[0])
                items.append({"id": item["id"], "wallet_id": item["wallet_id"], "binding_id": item["binding_id"],
                              "signal_id": item["signal_id"], "action": item["proposal"]["action"], "state": item["state"],
                              "temporal_status": "EXPIRED" if now >= item["proposal"]["expires_at"]*1000 else "CURRENT",
                              "reason": item["proposal"]["reason"], "expires_at": item["proposal"]["expires_at"],
                              "execution_id": filled[0] if filled else None})
            return items
        return response(read)
    return router
