"""Synthetic fixtures only: no exchange, paper execution or credentials."""
import copy
import hashlib
import json
import sqlite3

import pytest

from cryptolab.history.models import HistoryRequest, canonical_history, canonical_json, utc_iso
from cryptolab.history.storage import HistoryStore
from cryptolab.research.evidence.bundle import export_bundle, verify_bundle
from cryptolab.research.evidence.core import EvidenceError, canonical, digest, package, report, source_from_db, strict_json


@pytest.fixture
def evidence_data(settings, candles):
    store = HistoryStore(settings.database_path)
    store.migrate()
    req = HistoryRequest(symbol="BTCUSDT", interval="60", start=utc_iso(3600), end=utc_iso(3600*81))
    identifier, payload = canonical_history(req, candles)
    manifest = {"dataset_id": identifier, "sha256": identifier, "schema_version": 1, "source": "Bybit", "market": "spot",
                "symbol": req.symbol, "interval": req.interval, "start_time": req.start_time, "end_time": req.end_time,
                "candle_count": len(candles), "coverage_ratio": 1, "gaps": [], "integrity_status": "approved"}
    with store.connect() as db:
        db.execute("INSERT INTO historical_datasets VALUES (?,?,?,?,?,?,?,?,?)", (identifier, req.symbol, req.interval, req.start_time, req.end_time, len(candles), 1, canonical_json(manifest), payload))
    return settings.database_path, identifier, req.end_time*1000


def dump_database(path):
    with sqlite3.connect(path) as db:
        return list(db.iterdump())


def test_capture_export_offline_and_database_unchanged(evidence_data, tmp_path):
    path, identifier, end = evidence_data
    before = dump_database(path)
    source = source_from_db(path, identifier)
    first = package(source, "RETROSPECTIVE", end, end+100)
    second = package(source, "RETROSPECTIVE", end, end+200)
    assert first["content_hash"] == second["content_hash"]
    assert first["capture_id"] != second["capture_id"]
    assert first["validation"] == "UNVERIFIED_POINT_IN_TIME"
    rep = report(first, source, end+300)
    assert rep["report_content_hash"] == report(first, source, end+400)["report_content_hash"]
    bundle = tmp_path / "bundle"
    export_bundle(bundle, first, rep, source)
    assert verify_bundle(bundle)["content_hash"] == first["content_hash"]
    assert dump_database(path) == before
    with pytest.raises(EvidenceError):
        export_bundle(bundle, first, rep, source)


def test_canonical_and_domains():
    assert canonical({"á": 2, "a": 1}) == canonical({"a": 1, "á": 2})
    assert digest("a", {"x": "b"}) != digest("ab", {"x": "b"})
    assert digest("a", {"x": "1"}) != digest("a", {"x": "2"})
    for x in (1.0, float("nan"), float("inf")):
        with pytest.raises(EvidenceError): canonical({"x": x})
    with pytest.raises(EvidenceError): strict_json(b'{"x":1,"x":2}')


def test_temporal_source_and_tampering(evidence_data, tmp_path):
    path, identifier, end = evidence_data
    source = source_from_db(path, identifier)
    for asof, captured in ((end-1, end), (end, end-1), (-1, end), (True, end)):
        with pytest.raises(EvidenceError): package(source, "RETROSPECTIVE", asof, captured)
    with pytest.raises(EvidenceError): source_from_db(path, "0"*64)
    broken = copy.deepcopy(source)
    broken["payload"] += " "
    with pytest.raises(EvidenceError): package(broken, "RETROSPECTIVE", end, end)
    pkg = package(source, "RETROSPECTIVE", end, end)
    rep = report(pkg, source, end)
    bundle = tmp_path / "bundle"
    export_bundle(bundle, pkg, rep, source)
    (bundle / "report.json").write_text("{}", encoding="utf-8")
    with pytest.raises(EvidenceError): verify_bundle(bundle)


def test_offline_rejects_rehashed_forgery_and_extra_files(evidence_data, tmp_path):
    path, identifier, end = evidence_data
    source = source_from_db(path, identifier)
    pkg = package(source, "RETROSPECTIVE", end, end)
    rep = report(pkg, source, end)
    root = tmp_path / "bundle"
    export_bundle(root, pkg, rep, source)
    rep["verified_facts"][1]["value"] = 999999
    raw = canonical(rep)
    (root / "report.json").write_bytes(raw)
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"]["report.json"] = hashlib.sha256(raw).hexdigest()
    (root / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(EvidenceError): verify_bundle(root)


@pytest.mark.parametrize("mutation", ["unknown", "version", "reference", "symbol", "interval", "window"])
def test_rehashed_invalid_package_is_rejected(evidence_data, tmp_path, mutation):
    path, identifier, end = evidence_data
    source = source_from_db(path, identifier)
    pkg = package(source, "RETROSPECTIVE", end, end)
    rep = report(pkg, source, end)
    root = tmp_path / "bundle"
    export_bundle(root, pkg, rep, source)
    if mutation == "unknown": pkg["unexpected"] = True
    if mutation == "version": pkg["schema_version"] = 2
    if mutation == "reference": pkg["sources"][0]["source_id"] = "0"*64
    if mutation == "symbol": pkg["symbol"] = "ETHUSDT"
    if mutation == "interval": pkg["interval"] = "15"
    if mutation == "window": pkg["window"]["end_ms"] -= 3600000
    raw = canonical(pkg)
    (root / "evidence.json").write_bytes(raw)
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"]["evidence.json"] = hashlib.sha256(raw).hexdigest()
    (root / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(EvidenceError): verify_bundle(root)


def test_manifest_duplicate_and_missing_file(evidence_data, tmp_path):
    path, identifier, end = evidence_data
    source = source_from_db(path, identifier)
    pkg = package(source, "RETROSPECTIVE", end, end)
    root = tmp_path / "bundle"
    export_bundle(root, pkg, report(pkg, source, end), source)
    (root / "manifest.json").write_bytes(b'{"schema_version":1,"schema_version":1,"files":{}}')
    with pytest.raises(EvidenceError): verify_bundle(root)
    (root / "source.json").unlink()
    with pytest.raises(EvidenceError): verify_bundle(root)
    (root / "extra").write_text("unexpected")
    with pytest.raises(EvidenceError): verify_bundle(root)
