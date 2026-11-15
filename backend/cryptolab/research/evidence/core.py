"""Deterministic, read-only evidence for approved historical datasets."""
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from cryptolab.history.reader import DatasetReader
from cryptolab.history.storage import HistoryError

MAX_BYTES = 64 * 1024 * 1024  # accommodates the history limit of 100,000 candles
MAX_DEPTH = 64
HEX = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(ValueError):
    pass


def canonical(value):
    def check(obj, depth=0):
        if depth > MAX_DEPTH:
            raise EvidenceError("SCHEMA_INVALID")
        if obj is None or type(obj) in (str, int, bool):
            return
        if type(obj) is list:
            for item in obj:
                check(item, depth + 1)
        elif type(obj) is dict and all(type(k) is str for k in obj):
            for item in obj.values():
                check(item, depth + 1)
        else:
            raise EvidenceError("SCHEMA_INVALID")
    check(value)
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError):
        raise EvidenceError("SCHEMA_INVALID") from None


def digest(domain, value):
    return hashlib.sha256(domain.encode("ascii") + b"\0" + canonical(value)).hexdigest()


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise EvidenceError("SCHEMA_INVALID")
            out[key] = value
        return out
    if len(raw) > MAX_BYTES:
        raise EvidenceError("SIZE_LIMIT")
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        canonical(value)
        return value
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise EvidenceError("SCHEMA_INVALID") from None


def timestamp(value):
    if type(value) is not int or value < 0 or value > 253402300799999:
        raise EvidenceError("INVALID_TIMESTAMP")
    return value


class FrozenStore:
    """DatasetReader adapter over an already captured row, no database access."""
    def __init__(self, row):
        self.row = row

    @contextmanager
    def connect(self):
        class DB:
            def __init__(self, row): self.row = row
            def execute(self, sql, args):
                class Result:
                    def __init__(self, row): self.row = row
                    def fetchone(self): return self.row
                return Result(self.row if args[0] == self.row["id"] else None)
        yield DB(self.row)


def source_from_db(path, source_id):
    if not isinstance(source_id, str) or not HEX.fullmatch(source_id):
        raise EvidenceError("SOURCE_NOT_FOUND")
    try:
        uri = Path(path).resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            sizes = db.execute("SELECT length(CAST(payload AS BLOB)),length(CAST(manifest AS BLOB)),typeof(payload),typeof(manifest) FROM historical_datasets WHERE id=?", (source_id,)).fetchone()
            if sizes is None:
                raise EvidenceError("SOURCE_NOT_FOUND")
            if sizes[2:] != ("text", "text") or any(type(size) is not int for size in sizes[:2]):
                raise EvidenceError("SOURCE_UNVERIFIED")
            if sum(sizes[:2]) > MAX_BYTES:
                raise EvidenceError("SIZE_LIMIT")
            row = db.execute("SELECT id,payload,manifest FROM historical_datasets WHERE id=?", (source_id,)).fetchone()
            if row is None:
                raise EvidenceError("SOURCE_NOT_FOUND")
            source = {"id": row[0], "payload": row[1], "manifest": row[2]}
            if sum(len(v.encode("utf-8")) for v in source.values()) > MAX_BYTES:
                raise EvidenceError("SIZE_LIMIT")
            verify_source(source)
            return source
    except sqlite3.Error:
        raise EvidenceError("SOURCE_UNAVAILABLE") from None


def verify_source(source):
    if type(source) is not dict or set(source) != {"id", "payload", "manifest"} or not all(type(x) is str for x in source.values()):
        raise EvidenceError("SOURCE_UNVERIFIED")
    if not HEX.fullmatch(source["id"]):
        raise EvidenceError("SOURCE_UNVERIFIED")
    strict_json(source["payload"].encode())
    strict_json(source["manifest"].encode())
    try:
        dataset = DatasetReader(FrozenStore(source)).read(source["id"])
    except (HistoryError, ValueError, TypeError, OverflowError):
        raise EvidenceError("SOURCE_UNVERIFIED") from None
    return dataset


def package(source, mode, as_of_ms, captured_at_ms):
    if mode not in ("RETROSPECTIVE", "RECENT_OBSERVATION"):
        raise EvidenceError("SCHEMA_UNSUPPORTED")
    timestamp(as_of_ms); timestamp(captured_at_ms)
    data = verify_source(source)
    if data.end_time * 1000 > as_of_ms or as_of_ms > captured_at_ms:
        raise EvidenceError("TEMPORAL_LOOKAHEAD")
    manifest = data.manifest
    body = {"schema_version": 1, "mode": mode, "as_of_ms": as_of_ms,
            "symbol": manifest["symbol"], "interval": manifest["interval"],
            "window": {"start_ms": data.start_time * 1000, "end_ms": data.end_time * 1000},
            "sources": [{"source_kind": "approved-history", "source_id": source["id"],
                         "source_version": 1, "content_hash": source["id"],
                         "manifest_hash": hashlib.sha256(source["manifest"].encode("utf-8")).hexdigest(), "source_time_ms": None,
                         "fetched_at_ms": None, "available_at_ms": None,
                         "window": {"start_ms": data.start_time * 1000, "end_ms": data.end_time * 1000},
                         "provenance": "Bybit Spot; approved historical dataset", "verification_status": "UNVERIFIED_POINT_IN_TIME"}],
            "metrics": [], "assumptions": [], "missing": ["Historical availability not established"],
            "freshness": "UNKNOWN", "validation": "UNVERIFIED_POINT_IN_TIME"}
    content_hash = digest("escryptorio:evidence-content:v1", body)
    capture_id = digest("escryptorio:evidence-capture:v1", {"content_hash": content_hash, "captured_at_ms": captured_at_ms})
    return {**body, "content_hash": content_hash, "capture_id": capture_id, "captured_at_ms": captured_at_ms}


def report(pkg, source, generated_at_ms):
    timestamp(generated_at_ms)
    if generated_at_ms < pkg["captured_at_ms"]:
        raise EvidenceError("INVALID_TIMESTAMP")
    data = verify_source(source)
    ref = source["id"]
    body = {"schema_version": 1, "report_type": "DETERMINISTIC_REPORT", "evidence_package_id": pkg["capture_id"],
            "research_mode": pkg["mode"], "research_objective": "Describe verified historical dataset",
            "symbol": pkg["symbol"], "interval": pkg["interval"], "window": pkg["window"],
            "verified_facts": [{"name": "dataset_id", "value": ref, "evidence_ref": ref},
                               {"name": "candle_count", "value": len(data.candles), "evidence_ref": ref}],
            "metrics": [], "evidence_references": [ref], "observations": [],
            "missing_data": ["Historical availability not established"],
            "limitations": ["No investment recommendation or causal point-in-time claim", "Offline verification does not authenticate original source"],
            "uncertainty": ["Historical availability unknown"], "validation_result": "UNVERIFIED_POINT_IN_TIME",
            "generator_version": "deterministic-report/1"}
    content_hash = digest("escryptorio:report-content:v1", body)
    report_id = digest("escryptorio:report-generation:v1", {"report_content_hash": content_hash, "generated_at_ms": generated_at_ms})
    return {**body, "report_content_hash": content_hash, "report_id": report_id, "generated_at_ms": generated_at_ms}
