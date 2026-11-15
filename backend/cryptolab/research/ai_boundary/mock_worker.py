"""Standalone stdlib-only development fixture. This process is NOT SANDBOXED."""
import hashlib
import json
import sys

LIMIT = 65536


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(domain, value):
    return hashlib.sha256(domain.encode("ascii") + b"\0" + canonical(value)).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE")
        result[key] = value
    return result


def main():
    raw = sys.stdin.buffer.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("SIZE")
    request = json.loads(raw, object_pairs_hook=unique)
    if set(request) != {"schema_version", "request_id", "operation", "policy_version", "context", "input_hash"}:
        raise ValueError("SCHEMA")
    body = {k: v for k, v in request.items() if k != "input_hash"}
    if (type(request["schema_version"]) is not int or request["schema_version"] != 1
        or request["operation"] != "DESCRIBE_VERIFIED_CONTEXT"
        or request["policy_version"] != "development-mock/1"
        or request["input_hash"] != digest("escryptorio:worker-input:v1", body)):
        raise ValueError("REQUEST")
    context = request["context"]
    if context["schema_version"] != 1 or len(canonical(context)) > 32768:
        raise ValueError("CONTEXT")
    output = {
        "schema_version": 1, "request_id": request["request_id"],
        "context_id": context["context_id"], "context_hash": context["content_hash"],
        "worker_version": "mock-research/1", "status": "DESCRIBED",
        "observations": context["observations"], "evidence_refs": context["source_refs"],
        "limitations": context["limitations"], "uncertainty": context["uncertainty"],
        "point_in_time": context["point_in_time"], "analysis_scope": context["analysis_scope"],
        "usage": {"input_bytes": len(raw), "estimated_input_tokens": (len(raw) + 3) // 4},
    }
    output["output_hash"] = digest("escryptorio:worker-output:v1", output)
    sys.stdout.buffer.write(canonical(output))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, UnicodeError):
        sys.stderr.write("MOCK_INPUT_INVALID")
        sys.exit(2)
