"""SQLite event-sourced paper wallets. All ledger writes are local and atomic."""
import hashlib
import json
import re
import uuid
from decimal import Decimal, localcontext

from cryptolab.history.models import canonical_json, decimal_text
from cryptolab.paper.ledger import LEDGER_CONTEXT, LEDGER_VERSION, apply, initial_state
from cryptolab.paper.models import FillRecord, MarkRecord, StateRecord, WalletSpec
from cryptolab.storage import Store

GENESIS_KEY = "__genesis__"


class PaperError(ValueError):
    """Sanitized local ledger error."""


def _normalize(value):
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_normalize(v) for v in value]
    return value


def _hash(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _event_id(wallet_id: str, key: str) -> str:
    return hashlib.sha256((wallet_id + "\0" + key).encode("utf-8")).hexdigest()


def _key(value: str):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}", value) or value == GENESIS_KEY:
        raise PaperError("INVALID_IDEMPOTENCY_KEY")


def _state_payload(state):
    with localcontext(LEDGER_CONTEXT):
        return {**_normalize(state.model_dump()), "equity": _normalize(state.equity)}


def _event(wallet_id, sequence, key, kind, payload, previous_hash):
    body = {"schema_version": 1, "wallet_id": wallet_id, "sequence": sequence,
            "event_id": _event_id(wallet_id, key), "idempotency_key": key, "kind": kind,
            "payload": payload, "previous_hash": previous_hash}
    return {**body, "event_hash": _hash(body)}


class PaperStore(Store):
    def create_wallet(self, spec: WalletSpec, creation_key: str) -> dict:
        _key(creation_key)
        spec = WalletSpec.model_validate(spec.model_dump())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id FROM paper_wallets WHERE creation_key=?", (creation_key,)).fetchone()
            if existing:
                view, _ = self._replay(db, existing[0])
                if WalletSpec.model_validate(view["spec"]) != spec:
                    raise PaperError("IDEMPOTENCY_CONFLICT")
                return view
            if db.execute("SELECT 1 FROM paper_wallets WHERE bot_id=?", (spec.bot_id,)).fetchone():
                raise PaperError("BOT_ALREADY_EXISTS")
            wallet_id = uuid.uuid4().hex
            payload = {"schema_version": 1, "ledger_version": LEDGER_VERSION, "wallet_id": wallet_id, "creation_key": creation_key,
                       "spec": _normalize(spec.model_dump())}
            wallet_hash = _hash(payload)
            db.execute("INSERT INTO paper_wallets VALUES (?,?,?,?,?)", (wallet_id, spec.bot_id, creation_key,
                       canonical_json(payload), wallet_hash))
            state = initial_state(spec)
            event = _event(wallet_id, 1, GENESIS_KEY, "genesis",
                           {"input": None, "before": None, "after": _state_payload(state)}, wallet_hash)
            self._insert(db, event)
            db.execute("INSERT INTO paper_heads VALUES (?,?,?)", (wallet_id, 1, event["event_hash"]))
            view, _ = self._replay(db, wallet_id)
            return view

    @staticmethod
    def _insert(db, event):
        db.execute("INSERT INTO paper_events VALUES (?,?,?,?,?,?,?,?)", (event["wallet_id"], event["sequence"],
            event["event_id"], event["idempotency_key"], event["kind"], canonical_json(event["payload"]),
            event["previous_hash"], event["event_hash"]))

    def append(self, wallet_id: str, key: str, record: FillRecord | MarkRecord | StateRecord) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self.append_in_transaction(db, wallet_id, key, record)

    def append_in_transaction(self, db, wallet_id: str, key: str, record: FillRecord | MarkRecord | StateRecord) -> dict:
        """Apply an event using the caller's existing atomic write transaction."""
        if not db.in_transaction:
            raise PaperError("TRANSACTION_REQUIRED")
        _key(key)
        if isinstance(record, FillRecord):
            kind, model = "fill", FillRecord
        elif isinstance(record, MarkRecord):
            kind, model = "mark", MarkRecord
        elif isinstance(record, StateRecord):
            kind, model = "state", StateRecord
        else:
            raise PaperError("INVALID_EVENT_TYPE")
        record = model.model_validate(record.model_dump())
        requested = _normalize(record.model_dump())
        view, events = self._replay(db, wallet_id)
        previous = next((event for event in events if event["idempotency_key"] == key), None)
        if previous:
            if previous["kind"] != kind or previous["payload"]["input"] != requested:
                raise PaperError("IDEMPOTENCY_CONFLICT")
            return previous
        spec = WalletSpec.model_validate(view["spec"])
        from cryptolab.paper.models import WalletState
        state = WalletState.model_validate({k:v for k,v in view["state"].items() if k != "equity"})
        next_state = apply(state, spec, kind, requested)
        payload = {"input":requested, "before":_state_payload(state), "after":_state_payload(next_state)}
        event = _event(wallet_id, len(events)+1, key, kind, payload, events[-1]["event_hash"])
        self._insert(db, event)
        updated = db.execute("UPDATE paper_heads SET sequence=?,event_hash=? WHERE wallet_id=? AND sequence=? AND event_hash=?",
            (event["sequence"],event["event_hash"],wallet_id,len(events),events[-1]["event_hash"]))
        if updated.rowcount != 1:
            raise PaperError("CHECKPOINT_CONFLICT")
        return event

    def wallet(self, wallet_id: str) -> dict:
        with self.connect() as db:
            db.execute("BEGIN")
            view, _ = self._replay(db, wallet_id)
            return view

    def events(self, wallet_id: str) -> list[dict]:
        with self.connect() as db:
            db.execute("BEGIN")
            _, events = self._replay(db, wallet_id)
            return events

    def wallets(self) -> list[dict]:
        with self.connect() as db:
            db.execute("BEGIN")
            ids = [row[0] for row in db.execute("SELECT id FROM paper_wallets ORDER BY bot_id")]
            return [self._replay(db, wallet_id)[0] for wallet_id in ids]

    def _replay(self, db, wallet_id: str) -> tuple[dict, list[dict]]:
        row = db.execute("SELECT * FROM paper_wallets WHERE id=?", (wallet_id,)).fetchone()
        if row is None:
            raise PaperError("WALLET_NOT_FOUND")
        try:
            info = json.loads(row["payload"])
            if (canonical_json(info) != row["payload"] or _hash(info) != row["payload_hash"]
                or info["schema_version"] != 1 or info["ledger_version"] != LEDGER_VERSION or info["wallet_id"] != wallet_id
                or info["creation_key"] != row["creation_key"] or info["spec"]["bot_id"] != row["bot_id"]):
                raise ValueError("wallet")
            spec = WalletSpec.model_validate(info["spec"])
            head = db.execute("SELECT sequence,event_hash FROM paper_heads WHERE wallet_id=?", (wallet_id,)).fetchone()
            rows = db.execute("SELECT * FROM paper_events WHERE wallet_id=? ORDER BY sequence", (wallet_id,)).fetchall()
            if not head or not rows or len(rows) != head["sequence"]:
                raise ValueError("head")
            state = initial_state(spec)
            chain = row["payload_hash"]
            events = []
            for seq, entry in enumerate(rows, 1):
                payload = json.loads(entry["payload"])
                if entry["sequence"] != seq or canonical_json(payload) != entry["payload"]:
                    raise ValueError("sequence")
                event = _event(wallet_id, seq, entry["idempotency_key"], entry["kind"], payload, chain)
                if (entry["event_id"] != event["event_id"] or entry["previous_hash"] != chain
                    or entry["event_hash"] != event["event_hash"]):
                    raise ValueError("hash")
                if seq == 1:
                    if (entry["kind"] != "genesis" or entry["idempotency_key"] != GENESIS_KEY
                        or payload != {"input":None,"before":None,"after":_state_payload(state)}):
                        raise ValueError("genesis")
                else:
                    _key(entry["idempotency_key"])
                    if payload["before"] != _state_payload(state):
                        raise ValueError("before")
                    state = apply(state, spec, entry["kind"], payload["input"])
                    if payload["after"] != _state_payload(state):
                        raise ValueError("after")
                chain = event["event_hash"]
                events.append(event)
            if chain != head["event_hash"]:
                raise ValueError("checkpoint")
            return {"wallet_id": wallet_id, "ledger_version":info["ledger_version"], "spec":_normalize(spec.model_dump()), "state":_state_payload(state),
                    "sequence":len(events), "head_hash":chain, "wallet_hash":row["payload_hash"]}, events
        except (ValueError, KeyError, TypeError, ArithmeticError, json.JSONDecodeError):
            raise PaperError("LEDGER_INTEGRITY_ERROR") from None
