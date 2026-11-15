"""Reconcile claims to frozen backtest metrics; no simulation is run."""
from decimal import Decimal, InvalidOperation

from .backtest import verify_backtest
from .claims import CLAIM_DOMAIN, FIELDS, MAX_CLAIMS, RESULT_DOMAIN
from .core import EvidenceError, HEX, canonical, digest, timestamp

METRICS = {"net_return_pct": "percent", "max_drawdown_pct": "percent", "pnl": "USDT",
           "final_equity": "USDT", "fees": "USDT", "total_costs": "USDT", "closed_trades": "count"}


def validate_metrics(frozen, claims, as_of_ms):
    timestamp(as_of_ms)
    if type(claims) is not list or len(claims) > MAX_CLAIMS:
        raise EvidenceError("CLAIM_SCHEMA_INVALID")
    data, result = verify_backtest(frozen)
    if data.end_time * 1000 > as_of_ms:
        raise EvidenceError("TEMPORAL_LOOKAHEAD")
    m = result.manifest
    window = {"start_ms": m.start_time * 1000, "end_ms": m.end_time * 1000}
    metric_values = result.simulation.metrics.model_dump(mode="json")
    identifier = frozen["result"]["id"]
    output = []
    for c in claims:
        code, verified = None, None
        structural = False
        try:
            if type(c) is not dict or set(c) != FIELDS or len(canonical(c)) > 4096:
                raise EvidenceError("CLAIM_SCHEMA_INVALID")
            body = {k: v for k, v in c.items() if k != "claim_id"}
            if (type(c["schema_version"]) is not int or c["schema_version"] != 1
                or type(c["claim_id"]) is not str or not HEX.fullmatch(c["claim_id"])
                or digest(CLAIM_DOMAIN, body) != c["claim_id"]
                or any(type(c[k]) is not str for k in ("claim_type", "predicate", "method", "unit", "subject_id", "availability_scope"))
                or c["availability_scope"] not in ("RETROSPECTIVE_ANALYSIS", "CAUSAL_INFORMATION")):
                raise EvidenceError("CLAIM_SCHEMA_INVALID")
            structural = True
            if c["claim_type"] != "VERIFIED_METRIC" or c["predicate"] not in METRICS:
                raise EvidenceError("CLAIM_UNSUPPORTED_TYPE")
            if c["subject_id"] != identifier or c["evidence_refs"] != [identifier]:
                raise EvidenceError("CLAIM_REFERENCE_MISMATCH")
            if c["method"] != "persisted-backtest/1": raise EvidenceError("CLAIM_METHOD_UNSUPPORTED")
            if c["unit"] != METRICS[c["predicate"]]: raise EvidenceError("CLAIM_UNIT_MISMATCH")
            if canonical(c["window"]) != canonical(window): raise EvidenceError("CLAIM_WINDOW_MISMATCH")
            verified = metric_values[c["predicate"]]
            if c["predicate"] == "closed_trades":
                if type(c["value"]) is not int or c["value"] != verified: raise EvidenceError("CLAIM_VALUE_MISMATCH")
            else:
                if type(c["value"]) is not str or len(c["value"]) > 128: raise EvidenceError("CLAIM_NUMERIC_INVALID")
                val = Decimal(c["value"])
                if not val.is_finite(): raise EvidenceError("CLAIM_NUMERIC_INVALID")
                if val != Decimal(verified): raise EvidenceError("CLAIM_VALUE_MISMATCH")
        except EvidenceError as exc:
            code = str(exc)
        except (InvalidOperation, KeyError, TypeError, ValueError):
            code = "CLAIM_SCHEMA_INVALID"
        status = "INVALID" if code else ("UNVERIFIED_POINT_IN_TIME" if c["availability_scope"] == "CAUSAL_INFORMATION" else "VALIDATED")
        if status == "UNVERIFIED_POINT_IN_TIME": code = "CLAIM_POINT_IN_TIME_UNVERIFIED"
        result_body = {"schema_version": 1, "claim_id": c.get("claim_id") if type(c) is dict and type(c.get("claim_id")) is str else None,
                       "status": status, "code": code, "verified_value": verified,
                       "structural_integrity": structural, "source_integrity": "VERIFIED_HASH_AND_LINKS",
                       "value_accuracy": "MISMATCH" if code == "CLAIM_VALUE_MISMATCH" else ("VERIFIED" if verified is not None and code not in ("CLAIM_NUMERIC_INVALID", "CLAIM_SCHEMA_INVALID") else "UNKNOWN"),
                       "temporal_compatibility": "INCOMPATIBLE" if code == "CLAIM_WINDOW_MISMATCH" else ("VERIFIED" if verified is not None else "UNKNOWN"),
                       "point_in_time": "UNVERIFIED_POINT_IN_TIME",
                       "method": "persisted-backtest/1", "limitations": ["Value reconciled to stored result; simulation not recomputed", "No proof of historical availability or source authenticity"]}
        output.append({**result_body, "validation_id": digest(RESULT_DOMAIN, result_body)})
    return output
