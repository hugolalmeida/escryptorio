"""Durable recovery tests use only temporary directories and dictionary profiles."""
import json
import os
import pytest
from test_profile_plan import FakeProfiles
from cryptolab.research.ai_boundary.profile_plan import ProfilePolicy, ProfileLifecycle
from cryptolab.research.ai_boundary.profile_journal import Journal, Record, read_record, recovery_decision
from cryptolab.research.evidence.core import EvidenceError


def make(tmp_path):
    return Journal(tmp_path, Record(operation_id="1"*64, ownership_token="2"*64,
        policy_id=ProfilePolicy().policy_id, expected_sid="synthetic-owned-sid",
        created_at_ms=1, last_transition_ms=1))


def test_lifecycle_durable_and_crash_readonly(tmp_path):
    journal = make(tmp_path)
    lifecycle = ProfileLifecycle(journal=journal)
    lifecycle.exercise_mock(FakeProfiles(), lambda: None)
    restored = read_record(journal.path, "1"*64, "2"*64)
    assert restored.state == "CLEANED" and restored.generation == 6
    assert recovery_decision(restored, None) == "CLEANED_REQUIRES_STORAGE_VERIFICATION"
    with pytest.raises(FileExistsError):
        make(tmp_path)
    with pytest.raises(EvidenceError):
        journal.transition("CREATED")


@pytest.mark.parametrize("stage", ["fsync", "publish"])
def test_publish_failure_preserves_old_record(tmp_path, monkeypatch, stage):
    journal = make(tmp_path)
    original = journal.path.read_bytes()
    def fail(*args):
        raise OSError("synthetic")
    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync" if stage == "fsync" else "replace", fail)
        with pytest.raises(OSError): journal.transition("AUTHORIZED")
    assert journal.path.read_bytes() == original and journal.failed
    with pytest.raises(EvidenceError): journal.transition("AUTHORIZED")
    assert list(journal.root.iterdir()) == [journal.path]


@pytest.mark.parametrize("kind", ["hash", "operation", "owner", "truncated", "extra"])
def test_tampering_or_different_operation_rejected(tmp_path, kind):
    journal = make(tmp_path)
    obj = json.loads(journal.path.read_bytes())
    operation, owner = "1"*64, "2"*64
    if kind == "hash": obj["hash"] = "0"*64
    if kind == "extra": obj["unexpected"] = True
    if kind == "operation": operation = "3"*64
    if kind == "owner": owner = "3"*64
    journal.path.write_text("{" if kind == "truncated" else json.dumps(obj))
    with pytest.raises((EvidenceError, ValueError)):
        read_record(journal.path, operation, owner)


def test_uncertain_crash_never_authorizes_deletion(tmp_path):
    journal = make(tmp_path)
    journal.transition("AUTHORIZED")
    journal.transition("CREATING")
    record = read_record(journal.path, "1"*64, "2"*64)
    assert recovery_decision(record, "foreign") == "MANUAL_REVIEW_REQUIRED"
    with pytest.raises(EvidenceError):
        journal.transition("CREATED", observed_sid="S-1-5-999")


def test_native_mutations_blocked_without_instantiation():
    from cryptolab.research.ai_boundary.profile_native import NativeProfileAdapter
    adapter = NativeProfileAdapter.__new__(NativeProfileAdapter)
    with pytest.raises(EvidenceError, match="REQUIRES_APPROVAL"): adapter.create_profile()
    with pytest.raises(EvidenceError, match="REQUIRES_APPROVAL"): adapter.delete_profile()


def test_intent_write_failure_never_creates_profile(tmp_path, monkeypatch):
    journal, api = make(tmp_path), FakeProfiles()
    lifecycle = ProfileLifecycle(journal=journal)
    def fail(*args):
        raise OSError("synthetic")
    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError): lifecycle.exercise_mock(api, lambda: None)
    assert api.entries == {} and api.deleted == []


def test_readback_failure_does_not_reuse_published_generation(tmp_path, monkeypatch):
    from cryptolab.research.ai_boundary import profile_journal
    journal = make(tmp_path)
    original = profile_journal.read_record
    calls = 0
    def fail_readback(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise EvidenceError("SYNTHETIC_READBACK_FAILURE")
        return original(*args)
    with monkeypatch.context() as patch:
        patch.setattr(profile_journal, "read_record", fail_readback)
        with pytest.raises(EvidenceError): journal.transition("AUTHORIZED")
    assert journal.failed
    assert original(journal.path, "1"*64, "2"*64).state == "AUTHORIZED"
    with pytest.raises(EvidenceError): journal.transition("CREATING")
