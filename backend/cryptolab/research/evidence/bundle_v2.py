"""Version 2 backtest evidence bundles; v1 verification remains separate."""
import hashlib
import os
import shutil
import tempfile
from itertools import islice
from pathlib import Path

from .backtest import verify_backtest
from .core import EvidenceError, MAX_BYTES, canonical, digest, strict_json, timestamp
from .metrics import validate_metrics
from .claims import MAX_CLAIMS, validate_claims

FILES = ("evidence.json", "report.json", "frozen.json", "claims.json")


def build(frozen, claims, asof, captured, generated):
    timestamp(asof); timestamp(captured); timestamp(generated)
    if not asof <= captured <= generated:
        raise EvidenceError("TEMPORAL_LOOKAHEAD")
    data, result = verify_backtest(frozen)
    if type(claims) is not list or len(claims) > MAX_CLAIMS:
        raise EvidenceError("CLAIM_SCHEMA_INVALID")
    facts = [c for c in claims if type(c) is dict and c.get("claim_type") == "SOURCE_FACT"]
    metrics = [c for c in claims if type(c) is not dict or c.get("claim_type") != "SOURCE_FACT"]
    fact_results = iter(validate_claims(frozen["dataset"], facts))
    metric_results = iter(validate_metrics(frozen, metrics, asof))
    validations = [next(fact_results) if type(c) is dict and c.get("claim_type") == "SOURCE_FACT" else next(metric_results) for c in claims]
    manifest = result.manifest
    body = {"schema_version": 2, "mode": "RETROSPECTIVE", "as_of_ms": asof,
            "dataset_id": data.reference_hash, "protocol_id": frozen["protocol"]["id"],
            "result_id": frozen["result"]["id"], "symbol": manifest.symbol, "interval": manifest.interval,
            "window": {"start_ms": manifest.start_time * 1000, "end_ms": manifest.end_time * 1000},
            "frozen_hash": digest("escryptorio:backtest-frozen:v2", frozen),
            "availability": "UNVERIFIED_POINT_IN_TIME", "analysis_scope": "RETROSPECTIVE_ANALYSIS"}
    content_hash = digest("escryptorio:evidence-content:v2", body)
    capture_id = digest("escryptorio:evidence-capture:v2", {"content_hash": content_hash, "captured_at_ms": captured})
    pkg = {**body, "content_hash": content_hash, "capture_id": capture_id, "captured_at_ms": captured}
    report_body = {"schema_version": 2, "report_type": "DETERMINISTIC_REPORT", "evidence_package_id": capture_id,
                   "claim_validation_results": validations,
                   "verified_metrics": [v for c, v in zip(claims, validations) if type(c) is dict and c.get("claim_type") == "VERIFIED_METRIC" and v["status"] == "VALIDATED"],
                   "verified_facts": [v for c, v in zip(claims, validations) if type(c) is dict and c.get("claim_type") == "SOURCE_FACT" and v["status"] == "VALIDATED"], "missing_evidence": ["Historical point-in-time availability"],
                   "temporal_limitations": ["Analysis generation time and historical availability are not established"],
                   "methodological_limitations": ["Metrics reconciled to persisted result; no independent recalculation", "Historical simulation does not predict future returns"],
                   "source_warnings": {"result_id": frozen["result"]["id"], "warnings": list(result.warnings)},
                   "uncertainty": ["No external origin authentication"],
                   "provenance": {"dataset_id": data.reference_hash, "protocol_id": frozen["protocol"]["id"], "result_id": frozen["result"]["id"]},
                   "generator_version": "deterministic-report/2"}
    report_hash = digest("escryptorio:report-content:v2", report_body)
    report_id = digest("escryptorio:report-generation:v2", {"report_content_hash": report_hash, "generated_at_ms": generated})
    return pkg, {**report_body, "report_content_hash": report_hash, "report_id": report_id, "generated_at_ms": generated}


def export(destination, frozen, claims, asof, captured, generated):
    dest = Path(destination).absolute(); parent = dest.parent
    if dest.exists() or dest.is_symlink() or not parent.is_dir() or any(p.is_symlink() for p in (parent, *parent.parents)):
        raise EvidenceError("EXPORT_PATH_INVALID")
    pkg, rep = build(frozen, claims, asof, captured, generated)
    payloads = dict(zip(FILES, (canonical(x) for x in (pkg, rep, frozen, claims))))
    if any(len(x) > MAX_BYTES for x in payloads.values()): raise EvidenceError("SIZE_LIMIT")
    manifest = canonical({"schema_version": 2, "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()}})
    temp = Path(tempfile.mkdtemp(prefix=".evidence-", dir=parent))
    try:
        for name, raw in (*payloads.items(), ("manifest.json", manifest)):
            with (temp / name).open("xb") as out:
                out.write(raw); out.flush(); os.fsync(out.fileno())
        verify(temp)
        if dest.exists() or dest.is_symlink(): raise EvidenceError("EXPORT_PATH_INVALID")
        os.rename(temp, dest)
    finally:
        if temp.exists(): shutil.rmtree(temp)


def verify(path):
    root = Path(path).absolute()
    if not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
        raise EvidenceError("EXPORT_MANIFEST_INVALID")
    entries = list(islice(root.iterdir(), 6))
    if len(entries) != 5 or {p.name for p in entries} != set(FILES) | {"manifest.json"}:
        raise EvidenceError("EXPORT_MANIFEST_INVALID")
    raw = {}
    for entry in entries:
        if entry.is_symlink() or not entry.is_file() or entry.stat().st_size > MAX_BYTES:
            raise EvidenceError("EXPORT_MANIFEST_INVALID")
        with entry.open("rb") as handle: raw[entry.name] = handle.read(MAX_BYTES + 1)
        if len(raw[entry.name]) > MAX_BYTES: raise EvidenceError("SIZE_LIMIT")
    manifest = strict_json(raw["manifest.json"])
    if type(manifest) is not dict or set(manifest) != {"schema_version", "files"} or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 2 or type(manifest["files"]) is not dict or set(manifest["files"]) != set(FILES):
        raise EvidenceError("EXPORT_MANIFEST_INVALID")
    if any(manifest["files"][n] != hashlib.sha256(raw[n]).hexdigest() for n in FILES):
        raise EvidenceError("EVIDENCE_HASH_MISMATCH")
    pkg, rep, frozen, claims = (strict_json(raw[n]) for n in FILES)
    try:
        expected_pkg, expected_rep = build(frozen, claims, pkg["as_of_ms"], pkg["captured_at_ms"], rep["generated_at_ms"])
        if canonical(pkg) != canonical(expected_pkg) or canonical(rep) != canonical(expected_rep):
            raise EvidenceError("EVIDENCE_HASH_MISMATCH")
    except (KeyError, TypeError):
        raise EvidenceError("SCHEMA_INVALID") from None
    return {"capture_id": pkg["capture_id"], "content_hash": pkg["content_hash"], "report_id": rep["report_id"],
            "report_content_hash": rep["report_content_hash"], "validation": pkg["availability"]}
