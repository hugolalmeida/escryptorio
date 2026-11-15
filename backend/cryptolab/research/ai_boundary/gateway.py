"""Supervisor-owned request and independent deterministic output reconciliation."""
import re

from ..evidence.core import EvidenceError, canonical, digest, strict_json
from .contracts import parse_context


def make_request(context, request_id):
    if type(request_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
        raise EvidenceError("REQUEST_ID_INVALID")
    context = parse_context(canonical(context.model_dump(mode="json")))
    body = {"schema_version": 1, "request_id": request_id,
            "operation": "DESCRIBE_VERIFIED_CONTEXT", "policy_version": "development-mock/1",
            "context": context.model_dump(mode="json")}
    return canonical({**body, "input_hash": digest("escryptorio:worker-input:v1", body)})


def validate_output(raw, request, max_bytes):
    if type(raw) is not bytes or len(raw) > max_bytes:
        raise EvidenceError("OUTPUT_SIZE_LIMIT")
    if type(request) is not bytes or len(request) > 65536:
        raise EvidenceError("REQUEST_INVALID")
    req = strict_json(request)
    try:
        checked = make_request(parse_context(canonical(req["context"])), req["request_id"])
        if canonical(req) != checked:
            raise EvidenceError("REQUEST_INVALID")
    except (KeyError, TypeError):
        raise EvidenceError("REQUEST_INVALID") from None
    ctx = req["context"]
    # Construct independently of the worker. Exact reconciliation closes every
    # nested field and rejects added prose, omitted limitations and forged usage.
    expected = {
        "schema_version": 1, "request_id": req["request_id"],
        "context_id": ctx["context_id"], "context_hash": ctx["content_hash"],
        "worker_version": "mock-research/1", "status": "DESCRIBED",
        "observations": ctx["observations"], "evidence_refs": ctx["source_refs"],
        "limitations": ctx["limitations"], "uncertainty": ctx["uncertainty"],
        "point_in_time": ctx["point_in_time"], "analysis_scope": ctx["analysis_scope"],
        "usage": {"input_bytes": len(request), "estimated_input_tokens": (len(request) + 3) // 4},
    }
    expected["output_hash"] = digest("escryptorio:worker-output:v1", expected)
    if canonical(strict_json(raw)) != canonical(expected):
        raise EvidenceError("WORKER_OUTPUT_INVALID")
    return {"status": "VALIDATED_MOCK", "output": expected,
            "validation_id": digest("escryptorio:validation-gateway:v1", expected)}
