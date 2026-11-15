"""Disposable fixtures only. No real Create/DeleteAppContainerProfile calls."""
import ctypes as c
import json
import os
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from test_authorized_runner import FakeUserenv, Fixtures, request
from test_profile_journal import make
from test_profile_plan import FakeProfiles
from cryptolab.research.ai_boundary import profile_journal
from cryptolab.research.ai_boundary.authorized_runner import exercise_mock_runner, execute_authorized_test
from cryptolab.research.ai_boundary.journal_security import (
    WindowsJournalSecurity, reject_redirects, validate_journal_preflight)
from cryptolab.research.ai_boundary.profile_journal import Journal, read_record, recovery_decision
from cryptolab.research.ai_boundary.profile_native import PreparedNativeMutationContract, NativeProfileAdapter
from cryptolab.research.ai_boundary.profile_plan import ProfileLifecycle, ProfilePolicy
from cryptolab.research.ai_boundary.rollback_verification import verify_removal, ResourceObservations
from cryptolab.research.ai_boundary.windows_native import Native, SID_AND_ATTRIBUTES, WindowsErrorCode
from cryptolab.research.evidence.core import EvidenceError, canonical, digest


def cleaning(tmp_path):
    journal = make(tmp_path)
    for state in ("AUTHORIZED", "CREATING", "CREATED", "TESTING", "CLEANING"):
        journal.transition(state, observed_sid="synthetic-owned-sid" if state == "CREATED" else None)
    observations = Fixtures().cleanup_observations(journal, "synthetic-owned-sid")
    return journal, observations


@pytest.mark.parametrize("state,sid", [(state, sid) for state in
    ("AUTHORIZED", "CREATING", "CLEANING") for sid in (None, "synthetic-owned-sid", "S-1-5-999")])
def test_crash_recovery_never_retries_create_or_delete(tmp_path, state, sid):
    journal = make(tmp_path)
    for next_state in ("AUTHORIZED", "CREATING", "CREATED", "TESTING", "CLEANING"):
        journal.transition(next_state, observed_sid="synthetic-owned-sid" if next_state == "CREATED" else None)
        if next_state == state:
            break
    before = journal.path.read_bytes()
    assert recovery_decision(read_record(journal.path, "1"*64, "2"*64), sid) == "MANUAL_REVIEW_REQUIRED"
    assert journal.path.read_bytes() == before


@pytest.mark.parametrize("fault", ["fsync", "replace", "readback", "response_lost", "sid_lost"])
def test_created_but_uncommitted_never_deletes(tmp_path, monkeypatch, fault):
    journal, profiles = make(tmp_path), FakeProfiles()
    lifecycle = ProfileLifecycle(journal=journal)
    create = profiles.create
    def fail(*args): raise OSError("synthetic failure after Create")
    def create_and_fail(name, capabilities):
        sid = create(name, capabilities)
        assert journal.record.state == "CREATING"  # Intent precedes Create.
        if fault in ("response_lost", "sid_lost"):
            raise OSError("synthetic response lost")
        if fault == "readback":
            original = profile_journal.read_record
            calls = 0
            def readback(*args):
                nonlocal calls
                calls += 1
                if calls == 2: fail()
                return original(*args)
            monkeypatch.setattr(profile_journal, "read_record", readback)
        else:
            monkeypatch.setattr(os, fault, fail)
        return sid
    profiles.create = create_and_fail
    with pytest.raises(OSError): lifecycle.exercise_mock(profiles, lambda: pytest.fail("worker started"))
    assert profiles.entries and not profiles.deleted
    assert lifecycle.state == "ROLLBACK_REQUIRES_MANUAL_REVIEW"
    with pytest.raises(EvidenceError): lifecycle.exercise_mock(profiles, lambda: None)


@pytest.mark.parametrize("create_hr", [1, 2, 0x80004005, -2147024713])
def test_unexpected_or_signed_hresult_is_not_created(tmp_path, create_hr):
    api, journal = FakeUserenv(create_hr=create_hr), make(tmp_path)
    with pytest.raises(Exception):
        exercise_mock_runner(request(), journal, PreparedNativeMutationContract(api, "synthetic-owned-sid"), Fixtures())
    assert journal.record.state == "ROLLBACK_REQUIRES_MANUAL_REVIEW"
    assert not api.present


@pytest.mark.parametrize("field", ["process_stopped", "job_empty", "handles_released",
    "operation_directories_absent", "tree_absent", "delete_succeeded"])
@pytest.mark.parametrize("value,status", [(False, "RESIDUAL_RESOURCE_FOUND"), (None, "VERIFICATION_UNAVAILABLE")])
def test_missing_or_residual_resources_block_cleaned(tmp_path, field, value, status):
    journal, observations = cleaning(tmp_path)
    observations = ResourceObservations(**{**observations.model_dump(), field: value})
    result = verify_removal(journal, observations, FakeProfiles())
    assert result.status == status and field in result.details
    with pytest.raises(EvidenceError, match="ROLLBACK_INCOMPLETE"):
        journal.transition("CLEANED", cleanup_result=result)
    assert journal.record.state == "CLEANING"


@pytest.mark.parametrize("kind,status", [("profile", "PROFILE_PRESENT"),
    ("storage", "RESIDUAL_RESOURCE_FOUND"), ("registry_access", "VERIFICATION_UNAVAILABLE"),
    ("storage_access", "VERIFICATION_UNAVAILABLE"), ("unexpected", "VERIFICATION_ERROR"),
    ("wrong_sid", "VERIFICATION_ERROR"), ("owner", "VERIFICATION_ERROR")])
def test_readonly_removal_outcomes(tmp_path, kind, status):
    journal, observations = cleaning(tmp_path)
    profiles = FakeProfiles()
    original = profiles.inspect_profile
    def inspect():
        if kind in ("registry_access", "storage_access"): raise PermissionError("synthetic")
        if kind == "unexpected": raise RuntimeError("synthetic")
        return {**original(), "mapping_present": kind == "profile", "folder_present": kind == "storage",
                "expected_sid": "S-1-5-999" if kind == "wrong_sid" else "synthetic-owned-sid"}
    profiles.inspect_profile = inspect
    if kind == "owner":
        observations = ResourceObservations(**{**observations.model_dump(), "ownership_confirmed": False})
    before = journal.path.read_bytes()
    assert verify_removal(journal, observations, profiles).status == status
    assert before == journal.path.read_bytes() and not profiles.deleted


def test_cleaned_requires_independent_check_and_matching_operation(tmp_path):
    journal, observations = cleaning(tmp_path)
    with pytest.raises(EvidenceError): journal.transition("CLEANED")
    result = verify_removal(journal, observations, FakeProfiles())
    assert result.status == "PROFILE_ABSENT_IN_CHECKED_LOCATIONS"
    with pytest.raises(EvidenceError):
        journal.transition("CLEANED", cleanup_result=result.model_copy(update={"operation_id": "9"*64}))
    journal.transition("CLEANED", cleanup_result=result)
    assert recovery_decision(journal.record, None) == "CLEANED_REQUIRES_STORAGE_VERIFICATION"


def test_runner_residual_verification_overrides_worker_success(tmp_path):
    journal, profiles, fixtures = make(tmp_path), FakeProfiles(), Fixtures()
    original = fixtures.cleanup_observations
    fixtures.cleanup_observations = lambda *args: original(*args).model_copy(update={"job_empty": False})
    with pytest.raises(EvidenceError, match="ROLLBACK_INCOMPLETE"):
        exercise_mock_runner(request(), journal, profiles, fixtures)
    assert journal.record.state == "ROLLBACK_INCOMPLETE"
    with pytest.raises(EvidenceError):
        exercise_mock_runner(request(), journal, profiles, Fixtures())


@pytest.mark.parametrize("kind", ["same_bytes_replaced", "generation", "old_record", "corrupt"])
def test_journal_substitution_permanently_blocks_writer(tmp_path, kind):
    journal = make(tmp_path)
    before = journal.path.read_bytes()
    journal.transition("AUTHORIZED")
    if kind == "same_bytes_replaced":
        other = journal.root / "substitute"
        other.write_bytes(journal.path.read_bytes())
        os.replace(other, journal.path)
    elif kind == "corrupt": journal.path.write_bytes(b"{")
    elif kind == "old_record": journal.path.write_bytes(before)
    else:
        body = json.loads(journal.path.read_bytes())["record"]
        body["generation"] += 1
        journal.path.write_bytes(canonical({"record": body, "hash": digest("escryptorio:profile-journal:v1", body)}))
    with pytest.raises(Exception): journal.transition("CREATING")
    assert journal.failed
    with pytest.raises(EvidenceError): journal.transition("CREATING")


def test_concurrent_operation_and_transition_are_exclusive(tmp_path):
    journal = make(tmp_path)
    with pytest.raises(FileExistsError): make(tmp_path)
    def transition():
        try:
            journal.transition("AUTHORIZED")
            return "written"
        except EvidenceError: return "refused"
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: transition(), range(2))) == ["refused", "written"]
    assert journal.record.generation == 1


@pytest.mark.skipif(os.name != "nt", reason="Win32 ACL fixture")
def test_native_acl_readback_root_children_temp_manifest_and_tampering(tmp_path, monkeypatch):
    native = Native()
    token = native.current_token()
    try:
        info = native.token_info(token, 1)
        owner = native.sid_text(c.cast(info, c.POINTER(SID_AND_ATTRIBUTES)).contents.Sid)
    finally:
        native.close(token)
    root = tmp_path / "protected-journals"
    root.mkdir()
    sddl = f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{owner})"
    native.apply_dacl(root, sddl)
    guard = WindowsJournalSecurity(root)
    seed = make(tmp_path).record
    journal = Journal(root, seed, security=guard)
    published = []
    original = os.replace
    def replace(source, target):
        guard.check(Path(source))  # Verify actual temp ACL before publication.
        published.append(Path(source))
        return original(source, target)
    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", replace)
        exercise_mock_runner(request(), journal, FakeProfiles(), Fixtures())
    assert published and journal.record.state == "CLEANED"
    assert validate_journal_preflight(journal) == "JOURNAL_DACL_VERIFIED_WORKER_ACCESS_NOT_TESTED"
    native.apply_dacl(journal.path, sddl + "(A;;FA;;;WD)")
    with pytest.raises(EvidenceError, match="JOURNAL_SECURITY_NOT_VERIFIED"):
        validate_journal_preflight(journal)


@pytest.mark.skipif(os.name != "nt", reason="Win32 ACL fixture")
def test_permissive_acl_and_uncertain_owner_refused_before_create(tmp_path, monkeypatch):
    with pytest.raises(EvidenceError): WindowsJournalSecurity(tmp_path)
    # Owner parser is part of the rejection path, without changing fixture owner.
    native = Native()
    descriptor = native.file_security(tmp_path, 5)
    owner, control = native.security_owner_control(descriptor)
    assert owner.startswith("S-") and isinstance(control, int)
    with pytest.raises(EvidenceError): validate_journal_preflight(make(tmp_path))


@pytest.mark.skipif(os.name != "nt", reason="Win32 junction fixture")
def test_junction_in_parent_refused_and_not_followed(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    sentinel = target / "sentinel"
    sentinel.write_bytes(b"synthetic")
    link = tmp_path / "junction"
    # Only a newly named link in this disposable fixture; no target deletion.
    result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                            capture_output=True, check=False)
    assert result.returncode == 0
    try:
        assert link.lstat().st_file_attributes & 0x400
        with pytest.raises(EvidenceError): reject_redirects(link / "sentinel")
        with pytest.raises(EvidenceError): Journal(link, make(tmp_path).record)
    finally:
        link.rmdir()  # Remove only the verified fixture junction itself.
    assert sentinel.read_bytes() == b"synthetic"


@pytest.mark.parametrize("values", [{}, {"approve": True}, {"enable_native": True},
    {"evidence": {"status": "OS_ENFORCED_AND_TESTED"}}, {"config": {"authorization": True}}])
def test_execution_cannot_be_enabled_by_data(monkeypatch, values):
    monkeypatch.setenv("ENABLE_NATIVE", "true")
    with pytest.raises(EvidenceError, match="REQUIRES_APPROVAL"): execute_authorized_test(**values)


def test_prepared_contract_requires_strict_expected_sid():
    for sid in (None, "", "untrusted", True):
        with pytest.raises(ValueError): PreparedNativeMutationContract(FakeUserenv(), sid)


@pytest.mark.parametrize("stage", ["delete_response", "delete_confirmation"])
def test_delete_response_lost_never_retries_automatically(tmp_path, stage):
    journal, profiles = make(tmp_path), FakeProfiles()
    delete = profiles.delete
    def lost(name):
        delete(name)
        raise OSError("synthetic delete response lost")
    if stage == "delete_response": profiles.delete = lost
    else:
        def failed_confirmation(*args): raise PermissionError("synthetic confirmation unavailable")
        profiles.verify_cleanup = failed_confirmation
    with pytest.raises(OSError): ProfileLifecycle(journal=journal).exercise_mock(profiles, lambda: 7)
    assert not profiles.entries and journal.record.state == "ROLLBACK_INCOMPLETE"
    assert len(profiles.deleted) == 1
    assert recovery_decision(journal.record, None) == "MANUAL_REVIEW_REQUIRED"
    with pytest.raises(EvidenceError):
        ProfileLifecycle(journal=journal).exercise_mock(profiles, lambda: None)
    assert len(profiles.deleted) == 1


@pytest.mark.parametrize("fault", ["null_sid", "conversion", "free_sid", "wrong_sid"])
def test_partial_native_allocation_is_never_deleted(tmp_path, fault):
    journal, api = make(tmp_path), FakeUserenv()
    calls = []
    original_create = api.CreateAppContainerProfile
    def create(*args):
        hr = original_create(*args)
        if fault == "null_sid": c.cast(args[-1], c.POINTER(c.c_void_p))[0] = None
        return hr
    api.CreateAppContainerProfile = create
    if fault == "conversion":
        def fail(sid): raise WindowsErrorCode("synthetic", 5)
        api.sid_text = fail
    if fault == "free_sid": api.FreeSid = lambda sid: 123
    if fault == "wrong_sid": api.sid_text = lambda sid: "S-1-5-999"
    original_delete = api.DeleteAppContainerProfile
    def delete(name):
        calls.append(name)
        return original_delete(name)
    api.DeleteAppContainerProfile = delete
    with pytest.raises(Exception):
        exercise_mock_runner(request(), journal, PreparedNativeMutationContract(api, "synthetic-owned-sid"), Fixtures())
    assert api.present and not calls and journal.record.state == "ROLLBACK_REQUIRES_MANUAL_REVIEW"
    if fault in ("conversion", "wrong_sid"): assert api.freed == 1


def test_win32_access_denial_not_converted_to_absence(tmp_path):
    journal, observations = cleaning(tmp_path)
    class Denied:
        def inspect_profile(self): raise WindowsErrorCode("GetAppContainerFolderPath", 5)
    assert verify_removal(journal, observations, Denied()).status == "VERIFICATION_UNAVAILABLE"


@pytest.mark.parametrize("unsafe", ["relative", "network", "parent", "stream"])
def test_unexpected_journal_paths_refused(unsafe, tmp_path):
    path = {"relative": Path("relative"), "network": Path(r"\\server\share\journals"),
            "parent": tmp_path / ".." / "journals", "stream": tmp_path / "file:stream"}[unsafe]
    with pytest.raises(EvidenceError): reject_redirects(path)


@pytest.mark.skipif(os.name != "nt", reason="Win32 ACL fixture")
def test_owner_and_unprotected_dacl_rejected(tmp_path, monkeypatch):
    native = Native()
    token = native.current_token()
    try:
        info = native.token_info(token, 1)
        owner = native.sid_text(c.cast(info, c.POINTER(SID_AND_ATTRIBUTES)).contents.Sid)
    finally: native.close(token)
    root = tmp_path / "owned-fixture"
    root.mkdir()
    sddl = f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{owner})"
    native.apply_dacl(root, sddl)
    guard = WindowsJournalSecurity(root)
    with monkeypatch.context() as patch:
        patch.setattr(guard.native, "security_owner_control", lambda descriptor: ("S-1-5-999", 0x1000))
        with pytest.raises(EvidenceError): guard.check(root)
    with monkeypatch.context() as patch:
        patch.setattr(guard.native, "security_owner_control", lambda descriptor: (owner, 0))
        with pytest.raises(EvidenceError): guard.check(root)
    # Actual broad DACL, confined to the disposable fixture.
    native.apply_dacl(root, sddl + "(A;OICI;FA;;;WD)")
    with pytest.raises(EvidenceError): guard.check(root)


@pytest.mark.parametrize("transition,expected_deletes", [("CLEANING", 0), ("CLEANED", 1), ("ROLLBACK_INCOMPLETE", 0)])
def test_cleanup_journal_write_failure_preserves_error_and_blocks_reuse(tmp_path, monkeypatch, transition, expected_deletes):
    journal, profiles = make(tmp_path), FakeProfiles()
    lifecycle = ProfileLifecycle(journal=journal)
    original = journal._publish
    publications = []
    def publish(record):
        publications.append(record.state)
        if record.state == transition:
            journal.failed = True
            raise OSError("synthetic durable cleanup failure")
        original(record)
    monkeypatch.setattr(journal, "_publish", publish)
    if transition == "ROLLBACK_INCOMPLETE":
        def stop(): raise RuntimeError("synthetic stop failure")
        profiles.stop_and_release = stop
    with pytest.raises(OSError, match="synthetic durable cleanup failure"):
        lifecycle.exercise_mock(profiles, lambda: 7)
    assert lifecycle.state == "ROLLBACK_REQUIRES_MANUAL_REVIEW" and journal.failed
    assert len(profiles.deleted) == expected_deletes and publications[-1] == transition
    with pytest.raises(EvidenceError): lifecycle.exercise_mock(profiles, lambda: None)


def test_native_verification_refuses_unprotected_mock_journal(tmp_path):
    journal, observations = cleaning(tmp_path)
    observations = ResourceObservations(**{**observations.model_dump(), "source": "SUPERVISOR_READ_ONLY"})
    class MustNotInspect:
        def inspect_profile(self): pytest.fail("unprotected journal reached native inspection")
    result = verify_removal(journal, observations, MustNotInspect())
    assert result.status == "VERIFICATION_UNAVAILABLE"
    assert result.details == ("JOURNAL_SECURITY_NOT_VERIFIED",)
