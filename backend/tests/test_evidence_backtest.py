"""Backtest evidence tests use only synthetic research fixtures."""
import copy
import hashlib
import json
import sqlite3

import pytest

from test_backtest import research
from cryptolab.research.service import RunRequest
from cryptolab.research.evidence.backtest import freeze_backtest, verify_backtest
from cryptolab.research.evidence.claims import claim
from cryptolab.research.evidence.core import EvidenceError
from cryptolab.research.evidence.core import canonical
from cryptolab.research.evidence.metrics import validate_metrics
from cryptolab.research.evidence.bundle_v2 import export, verify


@pytest.fixture
def frozen(research):
    service, spec = research
    protocol = service.freeze(spec)
    result = service.run(RunRequest(protocol_id=protocol["id"], partition="train"))
    path = service.store.path
    with sqlite3.connect(path) as db: before = list(db.iterdump())
    source = freeze_backtest(path, result["id"])
    with sqlite3.connect(path) as db: assert list(db.iterdump()) == before
    return source, result, spec.test_end * 1000


def metric_body(result):
    m = result["manifest"]
    return {"schema_version": 1, "claim_type": "VERIFIED_METRIC", "subject_id": result["id"],
            "predicate": "net_return_pct", "value": result["simulation"]["metrics"]["net_return_pct"],
            "unit": "percent", "evidence_refs": [result["id"]],
            "window": {"start_ms": m["start_time"] * 1000, "end_ms": m["end_time"] * 1000},
            "method": "persisted-backtest/1", "availability_scope": "RETROSPECTIVE_ANALYSIS"}


def test_metric_reconciled_without_replay(frozen):
    source, result, asof = frozen
    valid = claim(metric_body(result))
    assert validate_metrics(source, [valid], asof)[0]["status"] == "VALIDATED"
    causal = metric_body(result); causal["availability_scope"] = "CAUSAL_INFORMATION"
    assert validate_metrics(source, [claim(causal)], asof)[0]["status"] == "UNVERIFIED_POINT_IN_TIME"
    with pytest.raises(EvidenceError, match="TEMPORAL_LOOKAHEAD"):
        validate_metrics(source, [valid], asof - 1)


@pytest.mark.parametrize("field,value,code", [("value", "999999", "CLAIM_VALUE_MISMATCH"),
    ("value", "NaN", "CLAIM_NUMERIC_INVALID"), ("value", 1.5, "CLAIM_SCHEMA_INVALID"),
    ("unit", "USDT", "CLAIM_UNIT_MISMATCH"), ("subject_id", "0" * 64, "CLAIM_REFERENCE_MISMATCH")])
def test_bad_metric(frozen, field, value, code):
    source, result, asof = frozen
    body = metric_body(result); body[field] = value
    if isinstance(value, float):
        with pytest.raises(EvidenceError): claim(body)
    else:
        checked = validate_metrics(source, [claim(body)], asof)[0]
        assert checked["status"] == "INVALID" and checked["code"] == code


@pytest.mark.parametrize("part", ["dataset", "protocol", "result"])
def test_tampered_frozen_backtest_fails(frozen, part):
    source, _, _ = frozen
    source = copy.deepcopy(source)
    source[part]["payload"] += " "
    with pytest.raises(EvidenceError): verify_backtest(source)


def test_v2_offline_bundle_and_tampering(frozen, tmp_path):
    source, result, asof = frozen
    root = tmp_path / "bundle"
    claims = [claim(metric_body(result))]
    export(root, source, claims, asof, asof, asof)
    assert verify(root)["validation"] == "UNVERIFIED_POINT_IN_TIME"
    with pytest.raises(EvidenceError): export(root, source, claims, asof, asof, asof)
    (root / "claims.json").write_text("[]", encoding="utf-8")
    with pytest.raises(EvidenceError): verify(root)


def test_v2_rehashed_claim_does_not_forge_validation(frozen, tmp_path):
    source, result, asof = frozen
    root = tmp_path / "bundle"
    claims = [claim(metric_body(result))]
    export(root, source, claims, asof, asof, asof)
    claims[0]["value"] = "999999"
    raw = canonical(claims)
    (root / "claims.json").write_bytes(raw)
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"]["claims.json"] = hashlib.sha256(raw).hexdigest()
    (root / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(EvidenceError): verify(root)
