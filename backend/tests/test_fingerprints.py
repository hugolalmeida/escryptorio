import shutil

import pytest

import cryptolab.research.fingerprint as fingerprint
import cryptolab.research.service as module
from cryptolab.research.service import ResearchError, RunRequest, digest
from test_backtest import research  # shared synthetic offline fixture

LEGACY = "85a5b51ab9a8a9a77e6e32f3ec887103b5dce701015077bf00b0335095d2168d"


@pytest.fixture
def source_copy(tmp_path, monkeypatch):
    copy = tmp_path / "backend"
    shutil.copytree(fingerprint.PACKAGE, copy / "cryptolab", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(fingerprint.BACKEND / "requirements.lock.txt", copy / "requirements.lock.txt")
    monkeypatch.setattr(module, "replay_fingerprint", lambda: fingerprint.replay_fingerprint(copy))
    return copy


def test_unrelated_code_lock_and_migration_leave_scoped_replay_unchanged(research, source_copy):
    service, spec = research
    protocol = service.freeze(spec)
    request = RunRequest(protocol_id=protocol["id"], partition="train")
    result = service.run(request)
    before = fingerprint.legacy_fingerprint(source_copy)
    (source_copy / "cryptolab" / "future_arena.py").write_text("# unrelated module\n", encoding="utf-8")
    (source_copy / "cryptolab" / "migrations" / "999_future.sql").write_text("SELECT 1;\n", encoding="utf-8")
    with (source_copy / "requirements.lock.txt").open("a", encoding="utf-8") as f:
        f.write("\nfuture-package==1\n")
    config = source_copy / "cryptolab" / "config.py"
    config.write_text(config.read_text(encoding="utf-8") + "\nUNRELATED_SETTING = 1\n", encoding="utf-8")
    service_file = source_copy / "cryptolab" / "research" / "service.py"
    source = service_file.read_text(encoding="utf-8")
    service_file.write_text(source.replace('raw["status"] != "Trading"', 'raw["status"] != "Other"'), encoding="utf-8")
    assert fingerprint.legacy_fingerprint(source_copy) != before
    assert service.run(request)["id"] == result["id"]
    assert service.verify(result["id"])["identical"]
    assert protocol["replay_dependencies"]["runtime"]["packages"]["pydantic"]


def test_relevant_math_change_requires_restart_and_new_protocol(research, source_copy, monkeypatch):
    service, spec = research
    protocol = service.freeze(spec)
    request = RunRequest(protocol_id=protocol["id"], partition="train")
    old = service.run(request)
    engine = source_copy / "cryptolab" / "engine" / "backtest.py"
    text = engine.read_text(encoding="utf-8")
    assert "reference*(1+config.costs.slippage_rate" in text
    engine.write_text(text.replace("reference*(1+config.costs.slippage_rate", "reference*(1-config.costs.slippage_rate"), encoding="utf-8")
    with pytest.raises(ResearchError, match="RESTART_REQUIRED"):
        service.run(request)
    with pytest.raises(ResearchError, match="RESTART_REQUIRED"):
        service.freeze(spec)
    # Emulate a fresh process fingerprint. No altered financial code is executed in this test.
    monkeypatch.setattr(module, "STARTUP_CODE_HASH", fingerprint.replay_fingerprint(source_copy)["code_hash"])
    with pytest.raises(ResearchError, match="ENGINE_CHANGED"):
        service.run(request)
    new = service.freeze(spec)
    assert new["id"] != protocol["id"] and new["code_hash"] != protocol["code_hash"]
    assert service.result(old["id"]) == old


def test_runtime_versions_are_part_of_hash(monkeypatch):
    before = fingerprint.replay_fingerprint()
    actual = fingerprint.version
    monkeypatch.setattr(fingerprint, "version", lambda name: "999.0" if name == "pydantic_core" else actual(name))
    after = fingerprint.replay_fingerprint()
    assert before["code_hash"] != after["code_hash"]
    assert after["replay_dependencies"]["runtime"]["packages"]["pydantic_core"] == "999.0"


def test_legacy_bridge_preserves_result_hash_and_rejects_unknown(research, source_copy, monkeypatch):
    service, spec = research
    # Exercise the bridge on any supported test runtime; the production mapping is
    # intentionally pinned to the separately audited Python 3.10.11 environment.
    monkeypatch.setitem(module.LEGACY_COMPATIBLE, LEGACY, fingerprint.replay_fingerprint(source_copy)["code_hash"])
    fresh = service.freeze(spec)
    old_protocol = {k: v for k, v in fresh.items() if k not in ("id", "fingerprint_scheme", "replay_dependencies")}
    old_protocol["code_hash"] = LEGACY
    old_id, payload = digest(old_protocol)
    with service.store.connect() as db:
        db.execute("INSERT INTO research_protocols(id,payload) VALUES (?,?)", (old_id, payload))
    request = RunRequest(protocol_id=old_id, partition="train")
    result = service.run(request)
    with service.store.connect() as db:
        stored_before = db.execute("SELECT payload FROM research_runs WHERE id=?", (result["id"],)).fetchone()[0]
        protocol_before = db.execute("SELECT payload FROM research_protocols WHERE id=?", (old_id,)).fetchone()[0]
    (source_copy / "cryptolab" / "independent.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert service.verify(result["id"])["identical"]
    assert service.protocol(old_id) == old_protocol
    with service.store.connect() as db:
        assert db.execute("SELECT payload FROM research_runs WHERE id=?", (result["id"],)).fetchone()[0] == stored_before
        assert db.execute("SELECT payload FROM research_protocols WHERE id=?", (old_id,)).fetchone()[0] == protocol_before
    old_protocol["code_hash"] = "1"*64
    unknown, payload = digest(old_protocol)
    with service.store.connect() as db:
        db.execute("INSERT INTO research_protocols(id,payload) VALUES (?,?)", (unknown, payload))
    with pytest.raises(ResearchError, match="ENGINE_CHANGED"):
        service.run(RunRequest(protocol_id=unknown, partition="train"))


def test_unknown_scheme_fails_closed(research):
    service, spec = research
    protocol = service.freeze(spec)
    value = {k: v for k, v in protocol.items() if k != "id"}
    value["fingerprint_scheme"] = "future/999"
    identifier, payload = digest(value)
    with service.store.connect() as db:
        db.execute("INSERT INTO research_protocols(id,payload) VALUES (?,?)", (identifier, payload))
    with pytest.raises(ResearchError, match="UNKNOWN_FINGERPRINT_SCHEME"):
        service.run(RunRequest(protocol_id=identifier, partition="train"))
