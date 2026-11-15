"""Structured claims against a synthetic historical dataset."""
import pytest

from test_evidence import evidence_data
from cryptolab.research.evidence.claims import claim, validate_claims
from cryptolab.research.evidence.core import source_from_db


def body(identifier, start, end, predicate="symbol", value="BTCUSDT", unit="symbol", scope="RETROSPECTIVE_ANALYSIS"):
    return {"schema_version": 1, "claim_type": "SOURCE_FACT", "subject_id": identifier,
            "predicate": predicate, "value": value, "unit": unit, "evidence_refs": [identifier],
            "window": {"start_ms": start, "end_ms": end}, "method": "dataset-reader/1", "availability_scope": scope}


def test_verified_facts_and_pit(evidence_data):
    path, identifier, end = evidence_data
    source = source_from_db(path, identifier)
    start = 3600000
    facts = [("dataset_id", identifier, "sha256"), ("symbol", "BTCUSDT", "symbol"),
             ("interval", "60", "interval"), ("candle_count", 80, "count"),
             ("window", {"start_ms": start, "end_ms": end}, "utc_ms")]
    claims = [claim(body(identifier, start, end, *fact)) for fact in facts]
    assert all(r["status"] == "VALIDATED" for r in validate_claims(source, claims))
    causal = claim(body(identifier, start, end, scope="CAUSAL_INFORMATION"))
    assert validate_claims(source, [causal])[0]["status"] == "UNVERIFIED_POINT_IN_TIME"


@pytest.mark.parametrize("field,value,code", [("value", "ETHUSDT", "CLAIM_VALUE_MISMATCH"),
    ("unit", "count", "CLAIM_UNIT_MISMATCH"), ("method", "unknown", "CLAIM_METHOD_UNSUPPORTED"),
    ("subject_id", "0" * 64, "CLAIM_REFERENCE_MISMATCH"), ("claim_type", "BUY", "CLAIM_UNSUPPORTED_TYPE")])
def test_wrong_claim_rejected(evidence_data, field, value, code):
    path, identifier, end = evidence_data
    source = source_from_db(path, identifier)
    data = body(identifier, 3600000, end, scope="CAUSAL_INFORMATION")
    data[field] = value
    result = validate_claims(source, [claim(data)])[0]
    assert result["status"] == "INVALID" and result["code"] == code


def test_tampered_id_and_prohibited_field_fail(evidence_data):
    path, identifier, end = evidence_data
    source = source_from_db(path, identifier)
    valid = claim(body(identifier, 3600000, end))
    valid["value"] = "ETHUSDT"
    assert validate_claims(source, [valid])[0]["code"] == "CLAIM_SCHEMA_INVALID"
    valid["execute_order"] = True
    assert validate_claims(source, [valid])[0]["code"] == "CLAIM_SCHEMA_INVALID"
