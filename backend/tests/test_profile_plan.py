"""All profile mutations in this file operate on a dictionary fixture."""
import pytest
from cryptolab.research.ai_boundary.profile_plan import ProfileLifecycle, ProfilePolicy, SecurityEvidence
from cryptolab.research.evidence.core import EvidenceError


class FakeProfiles:
    synthetic_only = True

    def __init__(self):
        self.entries = {}
        self.deleted = []

    def lookup(self, name):
        return self.entries.get(name)

    def create(self, name, capabilities):
        assert capabilities == ()
        self.entries[name] = "synthetic-owned-sid"
        return self.entries[name]

    def stop_and_release(self):
        pass

    def delete(self, name):
        self.deleted.append(name)
        del self.entries[name]


def test_default_disabled_and_contract():
    with pytest.raises(EvidenceError, match="REQUIRES_APPROVAL"):
        ProfileLifecycle().create()
    with pytest.raises(EvidenceError):
        ProfileLifecycle().exercise_mock(object(), lambda: None)
    for kwargs in ({"name":"other"}, {"capabilities":("internetClient",)}, {"extra":1}):
        with pytest.raises(ValueError):
            ProfilePolicy(**kwargs)
    assert ProfilePolicy().policy_id == ProfilePolicy().policy_id


def test_owned_cleanup_and_reuse_denied():
    api, lifecycle = FakeProfiles(), ProfileLifecycle()
    assert lifecycle.exercise_mock(api, lambda: 7) == 7
    assert lifecycle.state == "CLEANED" and api.entries == {}
    with pytest.raises(EvidenceError, match="STATE_INVALID"):
        lifecycle.exercise_mock(api, lambda: None)


@pytest.mark.parametrize("stage", ["acl", "launch", "job", "resume", "timeout", "cancel", "gateway"])
def test_operation_failure_cleans_owned_profile(stage):
    api, lifecycle = FakeProfiles(), ProfileLifecycle()
    def fail():
        raise RuntimeError(stage)
    with pytest.raises(RuntimeError):
        lifecycle.exercise_mock(api, fail)
    assert lifecycle.state == "CLEANED" and not api.entries


def test_preexisting_and_partial_are_never_deleted():
    api, lifecycle = FakeProfiles(), ProfileLifecycle()
    api.entries[lifecycle.policy.name] = "foreign"
    with pytest.raises(EvidenceError, match="ALREADY_EXISTS"):
        lifecycle.exercise_mock(api, lambda: None)
    assert api.deleted == []
    api.entries.clear()
    def partial(name, capabilities):
        api.entries[name] = "uncertain"
        raise OSError()
    api.create = partial
    with pytest.raises(OSError):
        lifecycle.exercise_mock(api, lambda: None)
    assert lifecycle.state == "ROLLBACK_REQUIRES_MANUAL_REVIEW" and api.deleted == []


@pytest.mark.parametrize("failure", ["delete", "verify", "ownership", "stop"])
def test_incomplete_cleanup_blocks_reuse(failure):
    api, lifecycle = FakeProfiles(), ProfileLifecycle()
    def operation():
        if failure == "delete":
            def fail(name):
                raise OSError()
            api.delete = fail
        elif failure == "verify":
            api.delete = lambda name: None
        elif failure == "ownership":
            api.entries[lifecycle.policy.name] = "foreign"
        else:
            def fail():
                raise KeyboardInterrupt()
            api.stop_and_release = fail
    with pytest.raises((OSError, EvidenceError, KeyboardInterrupt)):
        lifecycle.exercise_mock(api, operation)
    assert lifecycle.state in ("ROLLBACK_INCOMPLETE", "ROLLBACK_REQUIRES_MANUAL_REVIEW")
    with pytest.raises(EvidenceError):
        lifecycle.exercise_mock(api, lambda: None)


def test_security_evidence_closed_and_cannot_promote_filesystem():
    values = dict(policy_id=ProfilePolicy().policy_id, environment_id="0"*64,
                  isolation_identity="APPCONTAINER", process_creation_status="FAILED",
                  runtime_start_status="NOT_VERIFIED", resource_limits="NOT_VERIFIED",
                  rollback_result="COMPLETE", test_run_id="1"*64, observed_at_ms=1,
                  verification_status="NOT_VERIFIED", limitations=("PROFILE_NOT_AUTHORIZED",))
    evidence = SecurityEvidence(**values)
    with pytest.raises(ValueError):
        SecurityEvidence(**{**values,"filesystem_results":"ENFORCED_AND_TESTED"})
    with pytest.raises(ValueError):
        SecurityEvidence(**{**values,"private_path":"synthetic"})
    assert evidence.profile_ownership == "NONE"
