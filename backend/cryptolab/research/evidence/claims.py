"""Closed structured claims: no natural-language interpretation or execution."""
from .core import EvidenceError, HEX, canonical, digest, verify_source

CLAIM_DOMAIN = "escryptorio:claim:v1"
RESULT_DOMAIN = "escryptorio:claim-validation:v1"
MAX_CLAIMS = 100
FIELDS = {"schema_version", "claim_id", "claim_type", "subject_id", "predicate", "value", "unit", "evidence_refs", "window", "method", "availability_scope"}
FACTS = {"dataset_id": "sha256", "symbol": "symbol", "interval": "interval", "window": "utc_ms", "candle_count": "count"}


def claim(body):
    """Assign a domain-separated ID to a complete claim body."""
    if type(body) is not dict or "claim_id" in body:
        raise EvidenceError("CLAIM_SCHEMA_INVALID")
    return {**body, "claim_id": digest(CLAIM_DOMAIN, body)}


def validate_claims(source, claims):
    """Validate independent observations against one already frozen historical source."""
    if type(claims) is not list or len(claims) > MAX_CLAIMS:
        raise EvidenceError("CLAIM_SCHEMA_INVALID")
    data = verify_source(source)
    reference = source["id"]
    window = {"start_ms": data.start_time * 1000, "end_ms": data.end_time * 1000}
    facts = {"dataset_id": reference, "symbol": data.manifest["symbol"], "interval": data.manifest["interval"],
             "window": window, "candle_count": len(data.candles)}
    return [_validate(c, reference, window, facts) for c in claims]


def _validate(c, reference, window, facts):
    code = None
    value = None
    structural = False
    if type(c) is not dict or set(c) != FIELDS:
        code = "CLAIM_SCHEMA_INVALID"
    else:
        try:
            body = {k: v for k, v in c.items() if k != "claim_id"}
            structural = (type(c["schema_version"]) is int and c["schema_version"] == 1
                and len(canonical(c)) <= 4096
                and type(c["claim_id"]) is str and HEX.fullmatch(c["claim_id"]) is not None
                and all(type(c[k]) is str for k in ("claim_type", "predicate", "unit", "method", "availability_scope"))
                and c["claim_id"] == digest(CLAIM_DOMAIN, body)
                and type(c["subject_id"]) is str and HEX.fullmatch(c["subject_id"]) is not None
                and type(c["evidence_refs"]) is list and len(c["evidence_refs"]) == 1
                and type(c["evidence_refs"][0]) is str and HEX.fullmatch(c["evidence_refs"][0]) is not None
                and type(c["window"]) is dict and set(c["window"]) == {"start_ms", "end_ms"}
                and all(type(c["window"][k]) is int and c["window"][k] >= 0 for k in c["window"])
                and c["window"]["start_ms"] < c["window"]["end_ms"]
                and c["availability_scope"] in ("RETROSPECTIVE_ANALYSIS", "CAUSAL_INFORMATION"))
        except (TypeError, ValueError, EvidenceError):
            structural = False
        if not structural: code = "CLAIM_SCHEMA_INVALID"
        elif c["claim_type"] != "SOURCE_FACT" or c["predicate"] not in FACTS: code = "CLAIM_UNSUPPORTED_TYPE"
        elif c["evidence_refs"] != [reference] or c["subject_id"] != reference: code = "CLAIM_REFERENCE_MISMATCH"
        elif c["method"] != "dataset-reader/1": code = "CLAIM_METHOD_UNSUPPORTED"
        elif c["unit"] != FACTS[c["predicate"]]: code = "CLAIM_UNIT_MISMATCH"
        elif c["window"] != window: code = "CLAIM_WINDOW_MISMATCH"
        else:
            value = facts[c["predicate"]]
            if canonical(c["value"]) != canonical(value): code = "CLAIM_VALUE_MISMATCH"
    state = "INVALID" if code else ("UNVERIFIED_POINT_IN_TIME" if c["availability_scope"] == "CAUSAL_INFORMATION" else "VALIDATED")
    if state == "UNVERIFIED_POINT_IN_TIME": code = "CLAIM_POINT_IN_TIME_UNVERIFIED"
    result = {"schema_version": 1, "claim_id": c.get("claim_id") if type(c) is dict and type(c.get("claim_id")) is str else None,
              "status": state, "code": code, "structural_integrity": structural,
              "source_integrity": "VERIFIED", "verified_value": value,
              "value_accuracy": "MISMATCH" if code == "CLAIM_VALUE_MISMATCH" else ("VERIFIED" if value is not None else "UNKNOWN"),
              "temporal_compatibility": "INCOMPATIBLE" if code == "CLAIM_WINDOW_MISMATCH" else ("VERIFIED" if value is not None else "UNKNOWN"),
              "point_in_time": "UNVERIFIED_POINT_IN_TIME", "method": "dataset-reader/1",
              "limitations": ["Historical availability and external authenticity are not proven"]}
    return {**result, "validation_id": digest(RESULT_DOMAIN, result)}
