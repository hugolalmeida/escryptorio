"""Golden vectors from c97f00a and adversarial offline checks."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from test_evidence_backtest import frozen, metric_body, research
from cryptolab.research.evidence import bundle, cli
from cryptolab.research.evidence.bundle_v2 import export as export_v2
from cryptolab.research.evidence.backtest import verify_backtest
from cryptolab.research.evidence.claims import claim
from cryptolab.research.evidence.core import EvidenceError, canonical, strict_json
from cryptolab.research.evidence.metrics import validate_metrics
from cryptolab.history.models import canonical_json

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "evidence_v1_golden"
DEEP = FIXTURES / "evidence_v1_deep_golden"


def test_golden_v1_previous_code_and_bytes():
    expected = {"evidence.json": "65629ecde89fee495f5c4c86a4cf449c66b141decdcc53d3f0c35e38134c755a",
                "report.json": "0fe5a89712e8e62c05583c7189ea899f3a15dfb763400791832fe42a07ca0834",
                "source.json": "2e75c6f5341fa6808a9cf7e5913c1865e356c2390adeccedf64590bae453f4ff"}
    manifest = json.loads((GOLDEN / "manifest.json").read_bytes())
    assert manifest == {"schema_version": 1, "files": expected}
    assert (GOLDEN / "manifest.json").read_bytes() == canonical(manifest)
    for name, digest in expected.items():
        assert hashlib.sha256((GOLDEN / name).read_bytes()).hexdigest() == digest
    result = bundle.verify_bundle(GOLDEN)
    assert result == {"content_hash": "6c42f41c6321f7039f9e90c45b4b6b0e32df30bde98a8e470abbdd8f9e960c3d",
        "capture_id": "a2c98b27d79f9d08432939866d886b6348b67f4a96f7ac7b1fb7befbc8ec9d24",
        "report_content_hash": "8c5ee827c3ba4db62ae012b978e8f97302d9a8496e97f952519e385722715cd8",
        "report_id": "09945152f1c58058d83a0230cdafe08ba4f8d7179874982eb21c1d6a51936973",
        "validation": "UNVERIFIED_POINT_IN_TIME"}


def test_v1_deep_legacy_golden():
    assert bundle.verify_bundle(DEEP)["content_hash"] == "f535553e7607d9dcbca8d0c4042d6e420d3649ee8a1ec954aafedabd960b66da"


@pytest.mark.parametrize("depth,valid", [(255, True), (256, True), (257, False)])
def test_legacy_depth_bound(depth, valid):
    nested = 0
    for _ in range(depth): nested = [nested]
    if valid: canonical(nested, max_depth=256)
    else:
        with pytest.raises(EvidenceError): canonical(nested, max_depth=256)


@pytest.mark.parametrize("depth,valid", [(63, True), (64, True), (65, False), (500, False)])
def test_depth_bounds(depth, valid):
    value = 0
    for _ in range(depth): value = [value]
    if valid: canonical(value)
    else:
        with pytest.raises(EvidenceError, match="SCHEMA_INVALID"): canonical(value)


@pytest.mark.parametrize("data", [b'{', b'\xff', b'{"a":1,"a":2}', b'NaN', b'Infinity', b'1.5'])
def test_invalid_json_rejected(data):
    with pytest.raises(EvidenceError): strict_json(data)


def run_cli(monkeypatch, capsys, args):
    monkeypatch.setattr(sys, "argv", ["evidence", *args])
    code = cli.main()
    return code, json.loads(capsys.readouterr().out)


def test_cli_manifest_dispatch_and_spoofed_layout(tmp_path, monkeypatch, capsys):
    root = tmp_path / "bundle"
    shutil.copytree(GOLDEN, root)
    code, output = run_cli(monkeypatch, capsys, ["verify", "--bundle", str(root)])
    assert code == 0 and output["bundle_schema_version"] == 1
    (root / "frozen.json").write_text('{}')
    code, output = run_cli(monkeypatch, capsys, ["verify", "--bundle", str(root)])
    assert code != 0 and output["validation"] == "INVALID"
    manifest = json.loads((root / "manifest.json").read_bytes()); manifest["schema_version"] = 2
    (root / "manifest.json").write_bytes(canonical(manifest))
    code, output = run_cli(monkeypatch, capsys, ["verify", "--bundle", str(root)])
    assert code != 0 and output["validation"] == "INVALID"
    manifest["schema_version"] = 3
    (root / "manifest.json").write_bytes(canonical(manifest))
    code, output = run_cli(monkeypatch, capsys, ["verify", "--bundle", str(root)])
    assert code != 0 and output["error"] == "SCHEMA_UNSUPPORTED"


def test_invalid_cli_arguments_are_json(monkeypatch, capsys):
    code, output = run_cli(monkeypatch, capsys, ["verify"])
    assert code == 1 and output == {"error": "ARGUMENT_INVALID", "validation": "INVALID"}


def test_cli_dispatches_v2_using_manifest(frozen, tmp_path, monkeypatch, capsys):
    source, result, asof = frozen
    target = tmp_path / "bundle"
    export_v2(target, source, [claim(metric_body(result))], asof, asof, asof)
    code, output = run_cli(monkeypatch, capsys, ["verify", "--bundle", str(target)])
    assert code == 0 and output["bundle_schema_version"] == 2


def test_claim_count_limit_and_duplicate_policy(frozen):
    source, result, asof = frozen
    c = claim(metric_body(result))
    checked = validate_metrics(source, [c, c], asof)
    assert len(checked) == 2 and checked[0] == checked[1]
    with pytest.raises(EvidenceError, match="CLAIM_SCHEMA_INVALID"):
        validate_metrics(source, [c] * 101, asof)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "unexpected.json"])
def test_manifest_paths_and_extra_names_rejected(tmp_path, name):
    root = tmp_path / "bundle"
    shutil.copytree(GOLDEN, root)
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"][name] = "0" * 64
    (root / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(EvidenceError): bundle.verify_bundle(root)


def test_symlink_file_is_rejected_when_supported(tmp_path):
    root = tmp_path / "bundle"
    shutil.copytree(GOLDEN, root)
    target = tmp_path / "outside.json"
    shutil.copyfile(root / "source.json", target)
    (root / "source.json").unlink()
    try:
        (root / "source.json").symlink_to(target)
    except OSError:
        pytest.skip("Windows does not permit symlink creation in this environment")
    with pytest.raises(EvidenceError): bundle.verify_bundle(root)


def test_v2_fsync_failure_leaves_no_bundle(frozen, tmp_path, monkeypatch):
    source, result, asof = frozen
    target = tmp_path / "output"
    before = {p.name for p in tmp_path.iterdir()}
    def fail(_): raise OSError("synthetic")
    monkeypatch.setattr("cryptolab.research.evidence.bundle_v2.os.fsync", fail)
    with pytest.raises(OSError): export_v2(target, source, [claim(metric_body(result))], asof, asof, asof)
    assert not target.exists() and {p.name for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("field,value", [("dataset_hash", "0"*64), ("protocol_id", "0"*64),
    ("engine_version", "unknown"), ("code_hash", "0"*64), ("strategy_version", "unknown"),
    ("start_time", 0), ("partition", "test")])
def test_rehashed_result_with_incompatible_links_is_rejected(frozen, field, value):
    import copy
    source, _, _ = frozen
    source = copy.deepcopy(source)
    data = json.loads(source["result"]["payload"])
    data["manifest"][field] = value
    payload = canonical_json(data)
    source["result"]["payload"] = payload
    source["result"]["id"] = hashlib.sha256(payload.encode()).hexdigest()
    with pytest.raises(EvidenceError): verify_backtest(source)


@pytest.mark.parametrize("field,value,expected", [("value", "Infinity", "CLAIM_NUMERIC_INVALID"),
    ("value", "1e999999999999999999999", "CLAIM_SCHEMA_INVALID"), ("unit", "USDT", "CLAIM_UNIT_MISMATCH"),
    ("window", {"start_ms": True, "end_ms": 1}, "CLAIM_WINDOW_MISMATCH")])
def test_metric_malformed_and_pit_precedence(frozen, field, value, expected):
    source, result, asof = frozen
    body = metric_body(result)
    body["availability_scope"] = "CAUSAL_INFORMATION"
    body[field] = value
    checked = validate_metrics(source, [claim(body)], asof)[0]
    assert checked["status"] == "INVALID" and checked["code"] == expected
