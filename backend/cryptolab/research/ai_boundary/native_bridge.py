"""Prepared ProfileOperationPort implementation, disconnected from every runner.

Default construction has NO mutation API. Only code can inject the dependency;
there is no native factory, CLI, configuration/worker authorization or flag. In
this phase only unit tests inject FakeUserenv. Future native wiring is a code
change requiring separate review and explicit human authorization.
"""
from .authorized_runner import TestPolicy, TestRequest
from .journal_security import validate_journal_preflight
from .os_receipts import OperationResources, same_operation
from .profile_journal import Journal, Record
from .profile_native import ProfileCallAPI, _ProfileMutationCalls
from .profile_plan import ProfilePolicy
from ..evidence.core import EvidenceError, canonical


class NativeProfileBridge:
    def __init__(self, journal: Journal, request: TestRequest, resources: OperationResources,
                 *, api: ProfileCallAPI | None = None):
        self.journal, self.request, self.resources, self.api = journal, request, resources, api
        if api is not None and (getattr(api, "provenance", None) not in ("TESTED_MOCK", "NATIVE_USERENV")
                                or not callable(getattr(api, "CreateAppContainerProfile", None))):
            raise EvidenceError("PROFILE_CREATION_REQUIRES_APPROVAL")
        if (type(resources) is not OperationResources or resources._bridge is not None
            or not same_operation(resources.operation, journal.record)
            or request.operation_id != journal.record.operation_id or request.policy_id != TestPolicy().policy_id):
            raise EvidenceError("BRIDGE_IDENTITY_INVALID")
        resources._bridge = self
        self.calls = _ProfileMutationCalls(api, journal.record.expected_sid) if api is not None else None
        self.failed = False
        self._owned = None

    def _check(self, operation: Record):
        try:
            self._check_bound(operation)
        except BaseException:
            self.failed = True
            raise

    def _check_bound(self, operation: Record):
        if self.api is None or self.calls is None:
            raise EvidenceError("PROFILE_CREATION_REQUIRES_APPROVAL")
        if (self.failed or self.journal.failed or type(operation) is not Record
            or operation != self.journal.record or not same_operation(operation, self.resources.operation)
            or operation.operation_id != self.request.operation_id or operation.policy_id != ProfilePolicy().policy_id):
            raise EvidenceError("BRIDGE_IDENTITY_OR_STATE_INVALID")
        token = self.api.discovery()
        if token.get("elevated") is not False or type(token.get("elevated")) is not bool or token.get("token_type") != 1:
            raise EvidenceError("NON_ELEVATED_TOKEN_REQUIRED")
        validate_journal_preflight(self.journal)
        self.journal._read_current()
        expected = canonical({"request": self.request.model_dump(mode="json"),
            "policy": TestPolicy().model_dump(mode="json"), "journal_ownership_token": operation.ownership_token})
        manifest = self.journal.root / "runner-request.json"
        with self.journal.pin(manifest):
            with manifest.open("rb") as stream:
                raw = stream.read(65537)
            if raw != expected:
                raise EvidenceError("BRIDGE_MANIFEST_INVALID")

    def _ambiguous(self):
        self.failed = True
        if not self.journal.failed:
            try:
                state = "ROLLBACK_REQUIRES_MANUAL_REVIEW" if self.journal.record.state == "CREATING" else "ROLLBACK_INCOMPLETE"
                self.journal.transition(state)
            except Exception:
                pass  # Preserve original error; never recover by deleting or retrying.

    def create_owned(self, operation: Record) -> str:
        try:
            self._check(operation)
            if operation.state != "AUTHORIZED" or self._owned is not None:
                raise EvidenceError("BRIDGE_STATE_INVALID")
            inspection = self.api.inspect_profile()
            if (inspection["profile_name"] != operation.profile_name or inspection["expected_sid"] != operation.expected_sid):
                raise EvidenceError("BRIDGE_PROFILE_IDENTITY_INVALID")
            if inspection["folder_present"] is not False or inspection["mapping_present"] is not False:
                raise EvidenceError("PROFILE_ALREADY_EXISTS")
        except BaseException:
            self.failed = True
            raise
        try:
            self.journal.transition("CREATING")  # Durable intent before ANY Create.
            with self.journal.pin(self.journal.path, self.journal.root / "runner-request.json"):
                validate_journal_preflight(self.journal)
                sid = self.calls.create(operation.profile_name, ProfilePolicy().capabilities)
            self.journal.transition("CREATED", observed_sid=sid)
            self._owned = (operation.operation_id, operation.ownership_token, sid)
            self.resources._created_sid = sid
            self.resources._profile_source = self.api.provenance
            self.resources._changed()
            return sid
        except BaseException:
            self._ambiguous()
            raise

    def delete_owned(self, operation: Record) -> None:
        self._check(operation)
        if (self._owned != (operation.operation_id, operation.ownership_token, operation.expected_sid)
            or operation.observed_sid != operation.expected_sid or operation.state not in ("CREATED", "TESTING", "CLEANING")):
            self.failed = True
            raise EvidenceError("ROLLBACK_REQUIRES_MANUAL_REVIEW")
        try:
            if operation.state != "CLEANING":
                self.journal.transition("CLEANING")
            observations = self.resources.collect(self.journal)
            self.resources.require_receipt(observations, self.journal, consume=True)
            if any(getattr(observations, key) is not True for key in
                   ("ownership_confirmed", "process_stopped", "job_empty", "handles_released")):
                raise EvidenceError("ROLLBACK_INCOMPLETE")
            with self.journal.pin(self.journal.path, self.journal.root / "runner-request.json"):
                validate_journal_preflight(self.journal)
                self.calls.delete(operation.profile_name)
                inspected = self.api.inspect_profile()
                if (inspected["expected_sid"] != operation.expected_sid
                    or inspected["profile_name"] != operation.profile_name
                    or inspected["mapping_present"] is not False or inspected["folder_present"] is not False):
                    raise EvidenceError("ROLLBACK_INCOMPLETE")
            self.resources._delete_succeeded = True
            self.resources._changed()
            self._owned = None
            # Never publishes CLEANED: independent removal verification is required.
        except BaseException:
            if self.calls.last_delete_hresult is not None:
                # A returned failure or confirmed residual is contrary evidence;
                # a lost response remains None. No real profile is tested here.
                self.resources._delete_succeeded = False
                self.resources._changed()
            self._ambiguous()
            raise
