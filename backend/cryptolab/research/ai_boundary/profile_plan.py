"""Inert profile lifecycle model. There is deliberately no native mutation adapter."""
from typing import Literal
from pydantic import Field
from .contracts import Closed, Hash
from ..evidence.core import EvidenceError, digest

PROFILE_NAME = "Escryptorio.PoC.D3A2.20261115.8c514dea"


class ProfilePolicy(Closed):
    schema_version: Literal[1] = 1
    name: Literal[PROFILE_NAME] = PROFILE_NAME
    capabilities: tuple[()] = ()
    authorization: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"

    @property
    def policy_id(self):
        return digest("escryptorio:profile-plan:v1", self.model_dump(mode="json"))


class SecurityEvidence(Closed):
    schema_version: Literal[1] = 1
    policy_id: Hash
    launcher_version: Literal["windows-isolation-poc/1"] = "windows-isolation-poc/1"
    environment_id: Hash
    isolation_identity: Literal["APPCONTAINER", "RESTRICTED_TOKEN", "JOB_ONLY"]
    profile_status: Literal["PROFILE_CREATION_REQUIRES_APPROVAL"] = "PROFILE_CREATION_REQUIRES_APPROVAL"
    profile_ownership: Literal["NONE"] = "NONE"
    process_creation_status: Literal["FAILED", "CREATED", "NOT_VERIFIED"]
    runtime_start_status: Literal["RUNTIME_INITIALIZATION_FAILED", "PROBE_STARTED", "NOT_VERIFIED"]
    resource_limits: Literal["NOT_VERIFIED", "ENFORCED_AND_TESTED"]
    filesystem_results: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"
    network_results: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"
    rollback_result: Literal["COMPLETE", "ROLLBACK_INCOMPLETE", "NOT_VERIFIED"]
    test_run_id: Hash
    observed_at_ms: int = Field(strict=True, ge=0, le=2**53-1)
    verification_status: Literal["PREPARED_NOT_EXECUTED", "NOT_VERIFIED"]
    limitations: tuple[Literal["PROFILE_NOT_AUTHORIZED", "NO_FILESYSTEM_OR_NETWORK_PROOF"], ...]


class ProfileLifecycle:
    """Models mock API transitions only. Native creation always fails closed."""
    def __init__(self, policy=None, journal=None):
        self.policy = policy or ProfilePolicy()
        self.owned_sid = None
        self.journal = journal
        self._state = "PLANNED"
        self.cleanup_result = None
        if journal is not None and (journal.record.state != "PLANNED" or journal.record.policy_id != self.policy.policy_id):
            raise EvidenceError("JOURNAL_IDENTITY_INVALID")

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        if self.journal is not None:
            try:
                self.journal.transition(value, observed_sid=self.owned_sid, cleanup_result=self.cleanup_result)
            except BaseException:
                if self.journal.failed:
                    self._state = "ROLLBACK_REQUIRES_MANUAL_REVIEW"
                raise
        self._state = value

    def create(self):
        raise EvidenceError("PROFILE_CREATION_REQUIRES_APPROVAL")

    def exercise_mock(self, api, operation):
        """Test seam, accepting only an explicitly synthetic adapter."""
        if getattr(api, "synthetic_only", False) is not True:
            raise EvidenceError("PROFILE_CREATION_REQUIRES_APPROVAL")
        if self.state != "PLANNED":
            raise EvidenceError("PROFILE_STATE_INVALID")
        if api.lookup(self.policy.name) is not None:
            raise EvidenceError("PROFILE_ALREADY_EXISTS")
        self.state = "AUTHORIZED"  # Synthetic authorization, never real consent.
        try:
            self.state = "CREATING"
            self.owned_sid = api.create(self.policy.name, self.policy.capabilities)
            if (not self.owned_sid or api.lookup(self.policy.name) != self.owned_sid
                or self.journal is not None and self.owned_sid != self.journal.record.expected_sid):
                self.state = "ROLLBACK_REQUIRES_MANUAL_REVIEW"
                raise EvidenceError(self.state)
            self.state = "CREATED"
            self.state = "TESTING"
            return operation()
        finally:
            if self.journal is not None and self.journal.failed:
                # Durable state may differ from memory. Preserve the original
                # error and resource; neither retry nor delete after write failure.
                self._state = "ROLLBACK_REQUIRES_MANUAL_REVIEW"
            elif self.owned_sid and self.state not in ("CREATING", "ROLLBACK_REQUIRES_MANUAL_REVIEW"):
                self.state = "CLEANING"
                try:
                    api.stop_and_release()
                    if api.lookup(self.policy.name) != self.owned_sid:
                        self.state = "ROLLBACK_REQUIRES_MANUAL_REVIEW"
                        raise EvidenceError(self.state)
                    api.delete(self.policy.name)
                    if api.lookup(self.policy.name) is not None:
                        raise EvidenceError("ROLLBACK_INCOMPLETE")
                    self.cleanup_result = api.verify_cleanup(self.journal, self.owned_sid)
                    if "OWNERSHIP_OR_JOURNAL_CONFLICT" in self.cleanup_result.details:
                        self.state = "ROLLBACK_REQUIRES_MANUAL_REVIEW"
                        raise EvidenceError(self.state)
                    if self.cleanup_result.status != "PROFILE_ABSENT_IN_CHECKED_LOCATIONS":
                        raise EvidenceError("ROLLBACK_INCOMPLETE")
                    self.state = "CLEANED"
                except BaseException:
                    if self.state != "ROLLBACK_REQUIRES_MANUAL_REVIEW" and not (self.journal and self.journal.failed):
                        self.state = "ROLLBACK_INCOMPLETE"
                    raise
            elif self.state == "CREATING":
                # Unknown partial creation must never be deleted by name alone.
                self.state = "ROLLBACK_REQUIRES_MANUAL_REVIEW"
