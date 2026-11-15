"""Trusted v2 projection. No database is supplied to the worker."""
import tempfile
from pathlib import Path

from ..evidence.bundle import manifest_version
from ..evidence.bundle_v2 import FILES, verify
from ..evidence.core import EvidenceError, MAX_BYTES, canonical, digest, strict_json
from .contracts import parse_context


def build_context(bundle):
    # Copy bounded files once, then verify and project that private snapshot.
    # The original directory must remain operator-controlled, as in evidence v2.
    root = Path(bundle).absolute()
    if manifest_version(root) != 2:
        raise EvidenceError("CONTEXT_REQUIRES_V2")
    if {p.name for p in root.iterdir()} != set(FILES) | {"manifest.json"}:
        raise EvidenceError("EXPORT_MANIFEST_INVALID")
    with tempfile.TemporaryDirectory(prefix="research-context-") as directory:
        snapshot = Path(directory)
        for name in (*FILES, "manifest.json"):
            path = root / name
            if path.is_symlink() or not path.is_file():
                raise EvidenceError("EXPORT_MANIFEST_INVALID")
            with path.open("rb") as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise EvidenceError("SIZE_LIMIT")
            (snapshot / name).write_bytes(raw)
        verify(snapshot)
        pkg = strict_json((snapshot / "evidence.json").read_bytes())
        report = strict_json((snapshot / "report.json").read_bytes())
        claims = strict_json((snapshot / "claims.json").read_bytes())
    observations = []
    for claim, validation in zip(claims, report["claim_validation_results"]):
        if validation["status"] == "VALIDATED":
            observations.append({
                "claim_id": claim["claim_id"], "validation_id": validation["validation_id"],
                "name": claim["predicate"], "value": validation["verified_value"],
                "unit": claim["unit"], "method": validation["method"],
                "source_ref": claim["subject_id"], "window": claim["window"],
                "status": "VALIDATED", "point_in_time": validation["point_in_time"],
                "limitations": validation["limitations"],
            })
    body = {
        "schema_version": 1, "builder_version": "research-context/1", "policy_version": "minimal-v2/1",
        "evidence_content_hash": pkg["content_hash"], "research_objective": "DESCRIBE_VERIFIED_CONTEXT",
        "mode": pkg["mode"], "symbol": pkg["symbol"], "interval": pkg["interval"],
        "as_of_ms": pkg["as_of_ms"], "window": pkg["window"],
        "source_refs": [pkg[k] for k in ("dataset_id", "protocol_id", "result_id")],
        "observations": observations, "rejected_claims": len(claims) - len(observations),
        "point_in_time": pkg["availability"], "analysis_scope": pkg["analysis_scope"],
        "limitations": report["temporal_limitations"] + report["methodological_limitations"]
                        + ["Source warnings withheld by minimization policy; consult trusted evidence report"],
        "uncertainty": report["uncertainty"], "missing_evidence": report["missing_evidence"],
    }
    identity = digest("escryptorio:research-context:v1", body)
    return parse_context(canonical({**body, "context_id": identity, "content_hash": identity}))
