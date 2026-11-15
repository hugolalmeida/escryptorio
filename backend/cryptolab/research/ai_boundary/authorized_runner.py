"""Reviewable runner preparation. Native execution has no enabled entry point."""
from typing import Literal
from pydantic import Field

from .contracts import Closed, Hash
from .profile_plan import PROFILE_NAME, ProfileLifecycle, ProfilePolicy
from .profile_native import NativeProfileAdapter
from .rollback_verification import verify_removal
from ..evidence.core import EvidenceError, canonical, digest


class TestPolicy(Closed):
    __test__ = False
    schema_version: int = Field(default=1, strict=True, ge=1, le=1)
    profile_name: Literal[PROFILE_NAME] = PROFILE_NAME
    capabilities: tuple[()] = ()
    runtime_path: Literal["worker/pythonw.exe"] = "worker/pythonw.exe"
    filesystem_policy: Literal["PROTECTED_DENY_ALLOWED_READ_OUTPUTS_WRITE"] = "PROTECTED_DENY_ALLOWED_READ_OUTPUTS_WRITE"
    network_policy: Literal["NO_CAPABILITIES_LOOPBACK_PROBE_ONLY"] = "NO_CAPABILITIES_LOOPBACK_PROBE_ONLY"
    memory_limit: Literal[67108864] = 67108864
    job_memory_limit: Literal[100663296] = 100663296
    process_limit: int = Field(default=1, strict=True, ge=1, le=1)
    timeout_ms: Literal[3000] = 3000
    authorization_status: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"

    @property
    def policy_id(self):
        return digest("escryptorio:authorized-test-policy:v1", self.model_dump(mode="json"))


class TestRequest(Closed):
    __test__ = False
    schema_version: int = Field(default=1, strict=True, ge=1, le=1)
    operation_id: Hash
    policy_id: Hash


def prepare_authorized_test(operation_id, inspector=None):
    policy = TestPolicy()
    request = TestRequest(operation_id=operation_id, policy_id=policy.policy_id)
    inspection = (inspector or NativeProfileAdapter()).prepare_creation()
    return {"request": request.model_dump(mode="json"), "policy": policy.model_dump(mode="json"),
            "profile_inspection": inspection, "status": "PROFILE_CREATION_REQUIRES_APPROVAL",
            "persistent_operations": ["CreateAppContainerProfile", "local recovery journal", "DeleteAppContainerProfile"],
            "future_journal_location": "%LOCALAPPDATA%/Escryptorio/IsolationPoC/journals; local volume and DACL to verify",
            "verification": "PREPARED_NOT_EXECUTED"}


def execute_authorized_test(*args, **kwargs):
    raise EvidenceError("PROFILE_CREATION_REQUIRES_APPROVAL")


def exercise_mock_runner(request, journal, profiles, fixtures):
    """Complete orchestration over synthetic adapters only, including cleanup."""
    if (getattr(profiles, "synthetic_only", False) is not True
        or getattr(fixtures, "synthetic_only", False) is not True):
        raise EvidenceError("PROFILE_CREATION_REQUIRES_APPROVAL")
    if (request.policy_id != TestPolicy().policy_id or request.operation_id != journal.record.operation_id
        or journal.record.policy_id != ProfilePolicy().policy_id):
        raise EvidenceError("RUNNER_IDENTITY_MISMATCH")
    if journal.failed or journal.record.state != "PLANNED":
        raise EvidenceError("JOURNAL_REQUIRES_MANUAL_REVIEW")
    manifest = canonical({"request": request.model_dump(mode="json"),
                          "policy": TestPolicy().model_dump(mode="json"),
                          "journal_ownership_token": journal.record.ownership_token})
    manifest_path = journal.root / "runner-request.json"
    journal.write_exclusive(manifest_path, manifest)
    lifecycle = ProfileLifecycle(journal=journal)
    # The existing journal binds the profile identity. The request independently
    # binds resource/runtime policy and operation, preserving legacy journal IDs.
    class BoundProfiles:
        synthetic_only = True
        create = staticmethod(profiles.create)
        lookup = staticmethod(profiles.lookup)

        @staticmethod
        def stop_and_release():
            fixtures.stop_and_release()
            profiles.stop_and_release()

        @staticmethod
        def delete(name):
            profiles.delete(name)
            if fixtures.remove_tree_and_verify() is not True:
                raise EvidenceError("ROLLBACK_INCOMPLETE")

        @staticmethod
        def verify_cleanup(current_journal, sid):
            observations = fixtures.cleanup_observations(current_journal, sid)
            if observations.source != "TESTED_MOCK":
                raise EvidenceError("ROLLBACK_INCOMPLETE")
            return verify_removal(current_journal, observations, profiles)

    def operation():
        fixtures.prepare_tree()
        fixtures.configure_acl()
        fixtures.launch_suspended_and_assign_job()
        if fixtures.confirm_runtime_identity() is not True:
            raise EvidenceError("RUNTIME_INITIALIZATION_FAILED")
        return fixtures.gateway(fixtures.run_probes())

    result = lifecycle.exercise_mock(BoundProfiles(), operation)
    return {"status": "TESTED_MOCK", "journal_state": journal.record.state,
            "profile_removed": profiles.lookup(PROFILE_NAME) is None,
            "result": result, "filesystem": "NOT_VERIFIED", "network": "NOT_VERIFIED"}
