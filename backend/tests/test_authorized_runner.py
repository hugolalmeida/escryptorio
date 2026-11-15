"""Native call contracts and end-to-end fixtures are exclusively synthetic."""
import ctypes as c
import pytest
from test_profile_journal import make
from test_profile_plan import FakeProfiles
from cryptolab.research.ai_boundary.authorized_runner import (
    TestPolicy, TestRequest, exercise_mock_runner, execute_authorized_test, prepare_authorized_test)
from cryptolab.research.ai_boundary.profile_native import PreparedNativeMutationContract
from cryptolab.research.ai_boundary.profile_plan import ProfileLifecycle
from cryptolab.research.evidence.core import EvidenceError


class Fixtures:
    synthetic_only = True

    def __init__(self, fail=None):
        self.fail = fail
        self.calls = []

    def step(self, name):
        self.calls.append(name)
        if name == self.fail:
            raise RuntimeError(name)

    def prepare_tree(self): self.step("tree")
    def configure_acl(self): self.step("acl")
    def launch_suspended_and_assign_job(self): self.step("launch")
    def confirm_runtime_identity(self):
        self.step("identity")
        return True
    def run_probes(self):
        self.step("probes")
        return {"synthetic": True}
    def gateway(self, result):
        self.step("gateway")
        assert result == {"synthetic": True}
        return {"validated_mock": True}
    def stop_and_release(self): self.step("stop")
    def remove_tree_and_verify(self):
        self.step("remove")
        return True


def request():
    return TestRequest(operation_id="1"*64, policy_id=TestPolicy().policy_id)


def test_mock_full_flow(tmp_path):
    journal, profiles, fixtures = make(tmp_path), FakeProfiles(), Fixtures()
    result = exercise_mock_runner(request(), journal, profiles, fixtures)
    assert result["status"] == "TESTED_MOCK" and result["journal_state"] == "CLEANED"
    assert not profiles.entries and fixtures.calls[-2:] == ["stop", "remove"]
    assert (journal.root / "runner-request.json").exists()


@pytest.mark.parametrize("failure", ["tree", "acl", "launch", "identity", "probes", "gateway", "stop", "remove"])
def test_failure_transitions_and_rollback(tmp_path, failure):
    journal, profiles, fixtures = make(tmp_path), FakeProfiles(), Fixtures(failure)
    with pytest.raises(RuntimeError):
        exercise_mock_runner(request(), journal, profiles, fixtures)
    expected = "ROLLBACK_INCOMPLETE" if failure in ("stop", "remove") else "CLEANED"
    assert journal.record.state == expected
    if failure == "stop": assert profiles.entries
    with pytest.raises((EvidenceError, FileExistsError)):
        exercise_mock_runner(request(), journal, profiles, Fixtures())


def test_sid_conflict_never_deletes_returned_profile(tmp_path):
    journal, profiles = make(tmp_path), FakeProfiles()
    original = profiles.create
    def wrong(name, capabilities):
        original(name, capabilities)
        profiles.entries[name] = "S-1-5-999"
        return "S-1-5-999"
    profiles.create = wrong
    with pytest.raises(EvidenceError, match="MANUAL_REVIEW"):
        ProfileLifecycle(journal=journal).exercise_mock(profiles, lambda: None)
    assert profiles.deleted == [] and journal.record.state == "ROLLBACK_REQUIRES_MANUAL_REVIEW"


def test_gates_and_policy():
    with pytest.raises(EvidenceError, match="REQUIRES_APPROVAL"):
        execute_authorized_test(approve=True)
    with pytest.raises(EvidenceError): PreparedNativeMutationContract(object(), "synthetic-owned-sid")
    for values in ({"runtime_path":"other.exe"}, {"capabilities":("internetClient",)}, {"extra":1},
                   {"schema_version":True}, {"process_limit":True}):
        with pytest.raises(ValueError): TestPolicy(**values)
    class ReadOnly:
        def prepare_creation(self): return {"status":"ABSENT_IN_INSPECTED_LOCATIONS"}
    assert prepare_authorized_test("1"*64, ReadOnly())["status"] == "PROFILE_CREATION_REQUIRES_APPROVAL"


def test_runner_policy_mismatch_never_creates(tmp_path):
    journal, profiles = make(tmp_path), FakeProfiles()
    bad = TestRequest(operation_id="1"*64, policy_id="0"*64)
    with pytest.raises(EvidenceError): exercise_mock_runner(bad, journal, profiles, Fixtures())
    assert not profiles.entries and journal.record.state == "PLANNED"


def test_manifest_fsync_failure_prevents_creation(tmp_path, monkeypatch):
    import os
    journal, profiles = make(tmp_path), FakeProfiles()
    def fail(*args): raise OSError("synthetic")
    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", fail)
        with pytest.raises(OSError): exercise_mock_runner(request(), journal, profiles, Fixtures())
    assert not profiles.entries and journal.record.state == "PLANNED"
    with pytest.raises(FileExistsError): exercise_mock_runner(request(), journal, profiles, Fixtures())


def test_unconfirmed_tree_absence_is_not_cleaned(tmp_path):
    journal, profiles, fixtures = make(tmp_path), FakeProfiles(), Fixtures()
    fixtures.remove_tree_and_verify = lambda: False
    with pytest.raises(EvidenceError, match="ROLLBACK_INCOMPLETE"):
        exercise_mock_runner(request(), journal, profiles, fixtures)
    assert journal.record.state == "ROLLBACK_INCOMPLETE"


class FakeUserenv:
    synthetic_only = True

    def __init__(self, create_hr=0, delete_hr=0, residual=False):
        self.create_hr, self.delete_hr, self.residual = create_hr, delete_hr, residual
        self.present = False
        self.freed = 0

    def lookup(self, name): return "synthetic-owned-sid" if self.present else None
    def sid_text(self, sid): return "synthetic-owned-sid"
    def FreeSid(self, sid):
        self.freed += 1
        return None
    def CreateAppContainerProfile(self, name, display, description, capabilities, count, output):
        assert capabilities is None and count == 0
        if self.create_hr == 0:
            self.present = True
            c.cast(output, c.POINTER(c.c_void_p))[0] = 123
        return self.create_hr
    def DeleteAppContainerProfile(self, name):
        if self.delete_hr == 0 and not self.residual: self.present = False
        return self.delete_hr
    def verify_storage_absent(self, name): return not self.present
    def stop_and_release(self): pass


def test_exact_native_call_bodies_with_fake_userenv(tmp_path):
    api = FakeUserenv()
    adapter = PreparedNativeMutationContract(api, "synthetic-owned-sid")
    result = exercise_mock_runner(request(), make(tmp_path), adapter, Fixtures())
    assert result["journal_state"] == "CLEANED" and api.freed == 1 and not api.present


@pytest.mark.parametrize("create_hr,delete_hr,residual", [(0x800700b7,0,False),(-2147024891,0,False),
    (1,0,False),(0,0x80070005,False),(0,0,True)])
def test_native_failures_are_not_success(tmp_path, create_hr, delete_hr, residual):
    api = FakeUserenv(create_hr, delete_hr, residual)
    adapter = PreparedNativeMutationContract(api, "synthetic-owned-sid")
    with pytest.raises(Exception): exercise_mock_runner(request(), make(tmp_path), adapter, Fixtures())
