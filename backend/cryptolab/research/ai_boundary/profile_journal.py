"""Bounded durable records. Recovery only inspects; it never deletes profiles."""
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Literal

from pydantic import Field
from .contracts import Closed, Hash
from .profile_plan import PROFILE_NAME, ProfilePolicy
from ..evidence.core import EvidenceError, canonical, digest, strict_json

State = Literal["PLANNED", "AUTHORIZATION_PENDING", "AUTHORIZED", "CREATING", "CREATED",
                "VERIFYING", "VERIFIED", "TESTING", "CLEANING", "CLEANED",
                "ROLLBACK_INCOMPLETE", "ROLLBACK_REQUIRES_MANUAL_REVIEW"]
EDGES = {"PLANNED": {"AUTHORIZATION_PENDING", "AUTHORIZED"},
         "AUTHORIZATION_PENDING": {"AUTHORIZED"}, "AUTHORIZED": {"CREATING"},
         "CREATING": {"CREATED", "CLEANING", "ROLLBACK_REQUIRES_MANUAL_REVIEW"},
         "CREATED": {"VERIFYING", "TESTING", "CLEANING"}, "VERIFYING": {"VERIFIED", "CLEANING"},
         "VERIFIED": {"TESTING", "CLEANING"}, "TESTING": {"CLEANING"},
         "CLEANING": {"CLEANED", "ROLLBACK_INCOMPLETE", "ROLLBACK_REQUIRES_MANUAL_REVIEW"}}


class Record(Closed):
    schema_version: Literal[1] = 1
    operation_id: Hash
    profile_name: Literal[PROFILE_NAME] = PROFILE_NAME
    policy_id: Hash
    ownership_token: Hash
    expected_sid: str = Field(pattern=r"^(S-[0-9]+(?:-[0-9]+)+|synthetic-owned-sid)$", max_length=184)
    observed_sid: str | None = Field(default=None, pattern=r"^(S-[0-9]+(?:-[0-9]+)+|synthetic-owned-sid)$", max_length=184)
    created_at_ms: int = Field(strict=True, ge=0)
    last_transition_ms: int = Field(strict=True, ge=0)
    generation: int = Field(default=0, strict=True, ge=0)
    state: State = "PLANNED"
    resource_manifest: tuple[Literal["PROFILE", "SYNTHETIC_TREE", "JOB", "LISTENER"], ...] = ()
    verification_status: Literal["NOT_VERIFIED", "MOCK_VERIFIED"] = "NOT_VERIFIED"


class Journal:
    """One instance owns an exclusively-created operation directory.

    Existing records are inspect-only through read_record. They cannot be opened
    as writable sessions after a crash, avoiding concurrent/stale writers.
    """
    def __init__(self, supervisor_root, record):
        if record.state != "PLANNED" or record.policy_id != ProfilePolicy().policy_id:
            raise EvidenceError("JOURNAL_IDENTITY_INVALID")
        root = Path(supervisor_root).absolute()
        if not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
            raise EvidenceError("JOURNAL_ROOT_INVALID")
        self.root = root / record.operation_id
        self.root.mkdir()  # Exclusive ownership; never reuse an existing operation.
        self.path = self.root / "journal.json"
        self.record = record
        self._lock = threading.Lock()
        self.failed = False
        self._publish(record)

    def _publish(self, record):
        body = record.model_dump(mode="json")
        raw = canonical({"record": body, "hash": digest("escryptorio:profile-journal:v1", body)})
        name = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as stream:
                name = stream.name
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            if read_record(self.path, record.operation_id, record.ownership_token) != record:
                raise EvidenceError("JOURNAL_READBACK_FAILED")
        except BaseException:
            self.failed = True
            raise
        finally:
            if name is not None and Path(name).exists():
                Path(name).unlink()

    def transition(self, state, observed_sid=None):
        with self._lock:
            if self.failed:
                raise EvidenceError("JOURNAL_REQUIRES_MANUAL_REVIEW")
            current = read_record(self.path, self.record.operation_id, self.record.ownership_token)
            if current != self.record or state not in EDGES.get(current.state, set()):
                raise EvidenceError("JOURNAL_TRANSITION_INVALID")
            values = current.model_dump()
            values.update(state=state, generation=current.generation + 1,
                          observed_sid=observed_sid or current.observed_sid,
                          last_transition_ms=max(current.last_transition_ms, time.time_ns() // 1000000))
            candidate = Record(**values)
            if state in ("CREATED", "CLEANED") and candidate.observed_sid != candidate.expected_sid:
                raise EvidenceError("JOURNAL_OWNERSHIP_CONFLICT")
            self._publish(candidate)
            self.record = candidate


def read_record(path, operation_id, ownership_token):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise EvidenceError("JOURNAL_PATH_INVALID")
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise EvidenceError("JOURNAL_SIZE_LIMIT")
    value = strict_json(raw)
    if type(value) is not dict or set(value) != {"record", "hash"}:
        raise EvidenceError("JOURNAL_INVALID")
    if type(value["record"]) is not dict or type(value["record"].get("schema_version")) is not int:
        raise EvidenceError("JOURNAL_INVALID")
    record = Record.model_validate_json(canonical(value["record"]))
    if (value["hash"] != digest("escryptorio:profile-journal:v1", value["record"])
        or record.operation_id != operation_id or record.ownership_token != ownership_token
        or record.policy_id != ProfilePolicy().policy_id):
        raise EvidenceError("JOURNAL_IDENTITY_INVALID")
    return record


def recovery_decision(record, observed_sid):
    """Read-only classification, including absence after a lost delete response."""
    if record.state == "CLEANED" and observed_sid is None:
        return "CLEANED_REQUIRES_STORAGE_VERIFICATION"
    return "MANUAL_REVIEW_REQUIRED"
