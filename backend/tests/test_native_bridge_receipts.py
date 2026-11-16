"""Real benign Child/Job/path observations; profile mutations only FakeUserenv."""
import ctypes as c
import os
from pathlib import Path
import subprocess

import pytest

from test_authorized_runner import FakeUserenv, request
from test_profile_journal import make
from cryptolab.research.ai_boundary.authorized_runner import TestPolicy, execute_authorized_test
from cryptolab.research.ai_boundary.isolation_poc import Child, IsolationPolicy, PocEnvironment
from cryptolab.research.ai_boundary.journal_security import WindowsJournalSecurity
from cryptolab.research.ai_boundary.native_bridge import NativeProfileBridge
from cryptolab.research.ai_boundary.os_receipts import DirectoryScope, OperationResources
from cryptolab.research.ai_boundary.profile_journal import Journal
from cryptolab.research.ai_boundary.profile_plan import PROFILE_NAME
from cryptolab.research.ai_boundary.profile_native import NativeProfileCalls, PreparedNativeMutationContract
from cryptolab.research.ai_boundary.rollback_verification import verify_removal
from cryptolab.research.ai_boundary.windows_native import Native, SID_AND_ATTRIBUTES, WindowsErrorCode
from cryptolab.research.ai_boundary.windows_paths import pinned_paths
from cryptolab.research.evidence.core import EvidenceError, canonical

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Win32 fixtures required")


def protected_journal(tmp_path):
    native = Native()
    token = native.current_token()
    try:
        info = native.token_info(token, 1)
        owner = native.sid_text(c.cast(info, c.POINTER(SID_AND_ATTRIBUTES)).contents.Sid)
    finally: native.close(token)
    root = tmp_path / "journals"
    root.mkdir()
    native.apply_dacl(root, f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{owner})")
    journal = Journal(root, make(tmp_path).record, security=WindowsJournalSecurity(root))
    journal.write_exclusive(journal.root / "runner-request.json", canonical({
        "request": request().model_dump(mode="json"), "policy": TestPolicy().model_dump(mode="json"),
        "journal_ownership_token": journal.record.ownership_token}))
    journal.transition("AUTHORIZED")
    return journal


class FakeProfileAPI(FakeUserenv):
    provenance = "TESTED_MOCK"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.creates = self.deletes = 0
    def discovery(self): return {"token_type": 1, "elevated": False}
    def CreateAppContainerProfile(self, *args):
        self.creates += 1
        return super().CreateAppContainerProfile(*args)
    def DeleteAppContainerProfile(self, name):
        self.deletes += 1
        return super().DeleteAppContainerProfile(name)


def simple_resources(tmp_path, operation, native=None):
    native = native or Native()
    root = tmp_path / "owned-tree"
    root.mkdir()
    return OperationResources(operation, native, DirectoryScope(native, root))


@pytest.fixture
def environment():
    with PocEnvironment() as value:
        yield value
    assert value.cleanup_state == "COMPLETE" and not value.root.exists()


def launch(environment, operation, probe="sleep", *, actual_job=None):
    native = environment.native
    resources = OperationResources(operation, native, DirectoryScope(native, environment.root, ("worker", "outputs")))
    job = native.job(IsolationPolicy(identity="JOB_ONLY"))
    resources.own_job(job)
    child = Child(native, resources=resources)
    streams = child.launch(environment.root, probe, actual_job or job, environment.sid, IsolationPolicy(identity="JOB_ONLY"))
    streams[0].write(b"{}")
    streams[0].close()
    return resources, child, job


def finish(resources, child, job):
    native = resources.native
    native.check(native.kernel.TerminateJobObject(job, 124), "TerminateJobObject")
    assert native.kernel.WaitForSingleObject(child.process, 3000) == 0
    assert child.cleanup() == []
    assert resources.observe_job() is True
    resources.close_job()


def test_real_live_and_terminated_process_job_handles(environment, tmp_path):
    journal = make(tmp_path)
    resources, child, job = launch(environment, journal.record)
    try:
        live = resources.collect(journal)
        assert live.source == "SUPERVISOR_READ_ONLY"
        assert live.process_stopped is False and live.job_empty is False
        assert resources.exit_code == 259 and resources.active_processes == 1
        assert live.handles_released is False and live.tree_absent is False
        assert live.ownership_confirmed is None and live.delete_succeeded is None
    finally: finish(resources, child, job)
    terminated = resources.collect(journal)
    assert terminated.process_stopped is True and terminated.job_empty is True
    assert resources.exit_code == 124 and resources.active_processes == 0
    assert terminated.handles_released is True
    resources.require_receipt(terminated, journal, consume=True)
    with pytest.raises(EvidenceError): resources.require_receipt(terminated, journal)
    assert terminated.tree_absent is False


def test_real_error_exit_is_stopped_not_success(environment, tmp_path):
    journal = make(tmp_path)
    resources, child, job = launch(environment, journal.record, "exit")
    try:
        assert environment.native.kernel.WaitForSingleObject(child.process, 3000) == 0
        receipt = resources.collect(journal)
        assert receipt.process_stopped is True and resources.exit_code != 0
    finally: finish(resources, child, job)


@pytest.mark.parametrize("fault", ["process", "job", "close"])
def test_os_query_or_close_failure_never_becomes_success(environment, tmp_path, monkeypatch, fault):
    resources, child, job = launch(environment, make(tmp_path).record)
    try:
        if fault == "process":
            with monkeypatch.context() as patch:
                patch.setattr(environment.native.kernel, "GetExitCodeProcess", lambda *args: 0)
                assert resources.collect().process_stopped is None
        elif fault == "job":
            def fail(*args): raise WindowsErrorCode("QueryInformationJobObject", 5)
            with monkeypatch.context() as patch:
                patch.setattr(environment.native, "job_accounting", fail)
                assert resources.collect().job_empty is None
        else:
            def fail(*args): raise WindowsErrorCode("CloseHandle", 5)
            with monkeypatch.context() as patch:
                patch.setattr(environment.native, "close", fail)
                with pytest.raises(WindowsErrorCode): child.close_handle(child.process)
                assert resources.handles_released() is False
    finally:
        # Failed close retains ownership. Actual fixture resources still cleaned.
        if fault == "close": resources.handles[child.process] = "OPEN"
        finish(resources, child, job)
    if fault == "close": assert resources.collect().handles_released is False


def test_foreign_job_membership_and_resource_claim_refused(environment, tmp_path, monkeypatch):
    other = environment.native.job(IsolationPolicy(identity="JOB_ONLY"))
    resources, child, job = launch(environment, make(tmp_path).record)
    try:
        query = environment.native.kernel.IsProcessInJob
        with monkeypatch.context() as patch:
            # Real OS query with another real Job, never a worker assertion.
            patch.setattr(environment.native.kernel, "IsProcessInJob", lambda process, job, output: query(process, other, output))
            assert resources.collect().process_stopped is None
        assert "ProcessQuery" in resources.errors
        foreign = simple_resources(tmp_path, resources.operation.model_copy(update={"operation_id": "9"*64}), environment.native)
        with pytest.raises(EvidenceError): foreign.track(job)
    finally:
        finish(resources, child, job)
        environment.native.close(other)


def test_receipt_rejects_copy_new_generation_foreign_operation_and_previous_observation(tmp_path):
    journal = make(tmp_path)
    resources = simple_resources(tmp_path, journal.record)
    old = resources.collect(journal)
    with pytest.raises(EvidenceError): resources.require_receipt(old.model_copy(), journal)
    new = resources.collect(journal)
    with pytest.raises(EvidenceError): resources.require_receipt(old, journal)
    resources.require_receipt(new, journal)
    journal.transition("AUTHORIZED")
    with pytest.raises(EvidenceError): resources.require_receipt(new, journal)
    with pytest.raises(EvidenceError): resources.collect(type("Foreign", (), {"failed": False,
        "record": journal.record.model_copy(update={"expected_sid": "S-1-5-999"})})())


def test_real_directory_presence_absence_and_access_error(tmp_path):
    resources = simple_resources(tmp_path, make(tmp_path).record)
    root = resources.directories.root
    assert resources.directories.observe() == (False, False)
    native = resources.native
    owner, _ = native.security_owner_control(native.file_security(root, 5))
    secure = f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{owner})"
    native.apply_dacl(root, f"D:P(D;;GR;;;{owner})(A;OICI;FA;;;SY)(A;OICI;FA;;;{owner})")
    try: assert resources.directories.observe() == (None, None)
    finally: native.apply_dacl(root, secure)
    root.rmdir()
    assert resources.directories.observe() == (True, True)
    root.mkdir()  # A different File ID cannot inherit the old tree's identity.
    assert resources.directories.observe() == (None, None)


def test_directory_escape_and_junction_rejected(tmp_path):
    resources = simple_resources(tmp_path, make(tmp_path).record)
    with pytest.raises(EvidenceError): DirectoryScope(resources.native, resources.directories.root, ("../outside",))
    root = resources.directories.root
    root.rmdir()
    target = tmp_path / "different"
    target.mkdir()
    result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(root), str(target)], capture_output=True)
    assert result.returncode == 0
    try: assert resources.directories.observe() == (None, None)
    finally: root.rmdir()
    assert target.exists()


def test_pinned_metadata_blocks_rename_write_and_reports_volume_file_id(tmp_path):
    journal = protected_journal(tmp_path)
    native = journal.security.native
    with journal.pin(journal.path) as held:
        handle, identity = held[journal.path]
        assert len(identity[1]) == 16 and identity[0] != 0
        assert native.file_handle_info(handle)[0] == identity
        with pytest.raises(OSError): journal.root.rename(journal.root.with_name("redirected"))
        with pytest.raises(OSError): journal.path.write_bytes(b"synthetic substitution")
        with pytest.raises(OSError): journal.path.rename(journal.root / "moved")
    assert journal._read_current().state == "AUTHORIZED"


def test_atomic_replace_same_bytes_different_file_id_poisoned(tmp_path, monkeypatch):
    journal = protected_journal(tmp_path)
    replace_file = os.replace
    def substitute(source, target):
        replace_file(source, target)
        other = journal.root / "attacker-fixture"
        other.write_bytes(Path(target).read_bytes())
        replace_file(other, target)
    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", substitute)
        with pytest.raises((EvidenceError, WindowsErrorCode, OSError)):
            journal.transition("CREATING")
    assert journal.failed
    with pytest.raises(EvidenceError): journal.transition("CREATING")


def test_published_file_id_mismatch_fails_closed(tmp_path, monkeypatch):
    journal = protected_journal(tmp_path)
    native = journal.security.native
    original = native.file_handle_info
    published = False
    replace_file = os.replace
    def replace(source, target):
        nonlocal published
        replace_file(source, target)
        published = True
    def differing_id(handle):
        identity, attributes, links = original(handle)
        if published and native.final_path(handle).endswith("journal.json"):
            identity = (identity[0], b"\xff" * 16)
        return identity, attributes, links
    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", replace)
        patch.setattr(native, "file_handle_info", differing_id)
        with pytest.raises(EvidenceError): journal.transition("CREATING")
    assert journal.failed


@pytest.mark.parametrize("fault", ["foreign_operation", "foreign_policy", "manifest", "elevated", "preexisting"])
def test_bridge_preconditions_no_create(tmp_path, fault):
    journal = protected_journal(tmp_path)
    resources = simple_resources(tmp_path, journal.record)
    api = FakeProfileAPI()
    bridge = NativeProfileBridge(journal, request(), resources, api=api)
    operation = journal.record
    if fault == "foreign_operation": operation = operation.model_copy(update={"operation_id": "9"*64})
    if fault == "foreign_policy": operation = operation.model_copy(update={"policy_id": "9"*64})
    if fault == "manifest": (journal.root / "runner-request.json").write_bytes(b"{}")
    if fault == "elevated": api.discovery = lambda: {"token_type": 1, "elevated": True}
    if fault == "preexisting": api.present = True
    with pytest.raises(EvidenceError): bridge.create_owned(operation)
    assert api.creates == 0 and api.deletes == 0 and bridge.failed
    api.present = False
    with pytest.raises(EvidenceError): bridge.create_owned(journal.record)
    assert api.creates == 0


@pytest.mark.parametrize("fault", ["s_false", "hresult", "wrong_sid", "lost_response", "before_journal", "after_journal"])
def test_bridge_create_ambiguity_does_not_delete_or_retry(tmp_path, monkeypatch, fault):
    journal = protected_journal(tmp_path)
    resources = simple_resources(tmp_path, journal.record)
    api = FakeProfileAPI(create_hr=1 if fault == "s_false" else 0x80004005 if fault == "hresult" else 0)
    bridge = NativeProfileBridge(journal, request(), resources, api=api)
    original_create = api.CreateAppContainerProfile
    def failure(*args): raise OSError("synthetic journal/API failure")
    def create(*args):
        assert journal.record.state == "CREATING"
        result = original_create(*args)
        if fault == "lost_response": failure()
        if fault == "after_journal": monkeypatch.setattr(os, "fsync", failure)
        return result
    api.CreateAppContainerProfile = create
    if fault == "wrong_sid": api.sid_text = lambda sid: "S-1-5-999"
    if fault == "before_journal": monkeypatch.setattr(os, "fsync", failure)
    with pytest.raises(Exception): bridge.create_owned(journal.record)
    assert api.deletes == 0 and bridge.failed
    assert resources._created_sid is None
    with pytest.raises(EvidenceError): bridge.create_owned(journal.record)


def test_bridge_mock_profile_with_real_resource_receipts_never_promotes_to_native(environment, tmp_path):
    journal = protected_journal(tmp_path)
    native = environment.native
    resources = OperationResources(journal.record, native, DirectoryScope(native, environment.root))
    api = FakeProfileAPI()
    bridge = NativeProfileBridge(journal, request(), resources, api=api)
    assert bridge.create_owned(journal.record) == "synthetic-owned-sid"
    assert journal.record.state == "CREATED" and api.freed == 1
    job = native.job(IsolationPolicy(identity="JOB_ONLY"))
    resources.own_job(job)
    child = Child(native, resources=resources)
    streams = child.launch(environment.root, "sleep", job, environment.sid, IsolationPolicy(identity="JOB_ONLY"))
    streams[0].write(b"{}")
    streams[0].close()
    finish(resources, child, job)
    bridge.delete_owned(journal.record)
    assert api.deletes == 1 and journal.record.state == "CLEANING"
    receipt = resources.collect(journal)
    assert receipt.source == "TESTED_MOCK" and receipt.delete_succeeded is True
    assert verify_removal(journal, receipt, api).status == "RESIDUAL_RESOURCE_FOUND"  # Tree remains.
    with pytest.raises(EvidenceError): journal.transition("CLEANED")


def test_default_bridge_and_executor_cannot_be_enabled_by_worker_data(tmp_path, monkeypatch):
    journal = protected_journal(tmp_path)
    resources = simple_resources(tmp_path, journal.record)
    bridge = NativeProfileBridge(journal, request(), resources)
    monkeypatch.setenv("ENABLE_NATIVE", "true")
    with pytest.raises(EvidenceError, match="REQUIRES_APPROVAL"): bridge.create_owned(journal.record)
    with pytest.raises(EvidenceError, match="REQUIRES_APPROVAL"): bridge.delete_owned(journal.record)
    with pytest.raises(EvidenceError, match="REQUIRES_APPROVAL"):
        execute_authorized_test(approve=True, evidence={"status": "BRIDGE_READY_FOR_HUMAN_REVIEW"})


def test_real_receipts_without_real_profile_cannot_publish_cleaned(tmp_path):
    journal = protected_journal(tmp_path)
    # Journal states are synthetic fixtures, never proof of an OS profile.
    for state in ("CREATING", "CREATED", "TESTING", "CLEANING"):
        journal.transition(state, observed_sid="synthetic-owned-sid" if state == "CREATED" else None)
    with PocEnvironment() as environment:
        resources, child, job = launch(environment, journal.record)
        finish(resources, child, job)
    receipt = resources.collect(journal)
    assert receipt.source == "SUPERVISOR_READ_ONLY"
    assert all(getattr(receipt, key) is True for key in ("process_stopped", "job_empty", "handles_released",
        "operation_directories_absent", "tree_absent"))
    assert receipt.ownership_confirmed is None and receipt.delete_succeeded is None
    forged = receipt.model_copy(update={"ownership_confirmed": True, "delete_succeeded": True})
    assert verify_removal(journal, forged, FakeProfileAPI(), collector=resources).status == "VERIFICATION_ERROR"
    result = verify_removal(journal, receipt, FakeProfileAPI(), collector=resources)
    assert result.status == "VERIFICATION_UNAVAILABLE"
    assert result.details == ("PROFILE_OWNERSHIP_NOT_VERIFIED",)
    with pytest.raises(EvidenceError): journal.transition("CLEANED", cleanup_result=result)
    with pytest.raises(EvidenceError): resources.track(123456)  # Operation sealed after consuming receipt.


@pytest.mark.parametrize("fault", ["active", "delete_hresult", "residual"])
def test_bridge_cleanup_incomplete_blocks_delete_or_reuse(environment, tmp_path, fault):
    journal = protected_journal(tmp_path)
    native = environment.native
    resources = OperationResources(journal.record, native, DirectoryScope(native, environment.root))
    api = FakeProfileAPI(delete_hr=0x80070005 if fault == "delete_hresult" else 0, residual=fault == "residual")
    bridge = NativeProfileBridge(journal, request(), resources, api=api)
    bridge.create_owned(journal.record)
    job = native.job(IsolationPolicy(identity="JOB_ONLY"))
    resources.own_job(job)
    child = Child(native, resources=resources)
    streams = child.launch(environment.root, "sleep", job, environment.sid, IsolationPolicy(identity="JOB_ONLY"))
    streams[0].write(b"{}")
    streams[0].close()
    try:
        if fault != "active": finish(resources, child, job)
        with pytest.raises((EvidenceError, WindowsErrorCode)): bridge.delete_owned(journal.record)
        assert journal.record.state == "ROLLBACK_INCOMPLETE" and bridge.failed
        assert resources.collect().delete_succeeded is (None if fault == "active" else False)
        if fault == "active": assert api.deletes == 0
        with pytest.raises(EvidenceError): bridge.delete_owned(journal.record)
    finally:
        if fault == "active": finish(resources, child, job)


def test_foreign_job_launch_is_refused_before_process_creation(environment, tmp_path):
    resources = OperationResources(make(tmp_path).record, environment.native, DirectoryScope(environment.native, environment.root))
    policy = IsolationPolicy(identity="JOB_ONLY")
    known, other = environment.native.job(policy), environment.native.job(policy)
    resources.own_job(known)
    child = Child(environment.native, resources=resources)
    try:
        with pytest.raises(EvidenceError): child.launch(environment.root, "sleep", other, environment.sid, policy)
        assert child.process is None and child.handles == []
    finally:
        resources.close_job()
        environment.native.close(other)


def test_win32_file_query_failure_poisoned_journal(tmp_path, monkeypatch):
    journal = protected_journal(tmp_path)
    def fail(*args): raise WindowsErrorCode("GetFileInformationByHandleEx", 5)
    with monkeypatch.context() as patch:
        patch.setattr(journal.security.native, "file_handle_info", fail)
        with pytest.raises(WindowsErrorCode): journal.transition("CREATING")
    assert journal.failed
    with pytest.raises(EvidenceError): journal.transition("CREATING")


def test_dll_facade_delegates_only_to_injected_fake_bindings():
    from types import SimpleNamespace
    api = FakeProfileAPI()
    # Bypass the real constructor: no DLL object is installed into this fixture.
    facade = NativeProfileCalls.__new__(NativeProfileCalls)
    facade.adapter = SimpleNamespace(native=SimpleNamespace(userenv=api, advapi=api,
        sid_text=api.sid_text, discovery=api.discovery), inspect_profile=api.inspect_profile)
    sid = c.c_void_p()
    assert facade.CreateAppContainerProfile(PROFILE_NAME, PROFILE_NAME, "synthetic", None, 0, c.byref(sid)) == 0
    assert facade.lookup(PROFILE_NAME) == "synthetic-owned-sid" and sid.value == 123
    assert facade.sid_text(sid) == "synthetic-owned-sid"
    assert facade.FreeSid(sid) is None
    assert facade.DeleteAppContainerProfile(PROFILE_NAME) == 0
    assert facade.verify_storage_absent(PROFILE_NAME) is True
    with pytest.raises(EvidenceError): facade.DeleteAppContainerProfile("another-profile")
    with pytest.raises(EvidenceError): facade.CreateAppContainerProfile(PROFILE_NAME, PROFILE_NAME, "synthetic", None, True, c.byref(sid))
    assert api.creates == api.deletes == api.freed == 1
    with pytest.raises(EvidenceError): PreparedNativeMutationContract(facade, "synthetic-owned-sid")
