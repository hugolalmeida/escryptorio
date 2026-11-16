"""Bounded durable records. Recovery only inspects; it never deletes profiles."""
import os
from pathlib import Path
import tempfile
import threading
import time
from contextlib import nullcontext
from typing import Literal

from pydantic import Field
from .contracts import Closed, Hash
from .profile_plan import PROFILE_NAME, ProfilePolicy
from .journal_security import reject_redirects
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
    def __init__(self, supervisor_root, record, *, security=None):
        if record.state != "PLANNED" or record.policy_id != ProfilePolicy().policy_id:
            raise EvidenceError("JOURNAL_IDENTITY_INVALID")
        root = Path(supervisor_root).absolute()
        reject_redirects(root)
        if not root.is_dir():
            raise EvidenceError("JOURNAL_ROOT_INVALID")
        self.security = security
        if security is not None:
            if security.root != root:
                raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
            security.check(root)
        self.root = root / record.operation_id
        with self.pin(root):
            self.root.mkdir()  # Exclusive ownership; never reuse an existing operation.
            if security is not None:
                security.protect_new(self.root)
        self.path = self.root / "journal.json"
        self.record = record
        self._lock = threading.Lock()
        self.failed = False
        self._published_identity = None
        self._published_file_id = None
        self._publish(record)

    def check_path(self, path):
        reject_redirects(path)
        if self.security is not None:
            self.security.check(path)

    def pin(self, *paths, allow_delete_files=False):
        return (self.security.pin(*paths, allow_delete_files=allow_delete_files)
                if self.security is not None else nullcontext({}))

    def write_exclusive(self, path, raw):
        """Protected, exclusive runner manifest; failure permanently poisons session."""
        try:
            with self.pin(self.root):
                self._write_exclusive_pinned(path, raw)
        except BaseException:
            self.failed = True
            raise

    def _write_exclusive_pinned(self, path, raw):
        try:
            if path != self.root / "runner-request.json" or self.failed:
                raise EvidenceError("JOURNAL_REQUIRES_MANUAL_REVIEW")
            self.check_path(self.root)
            with path.open("xb") as stream:
                created_identity = self._writer_identity(stream)
                if self.security is not None:
                    self.security.protect_new(path)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            with self.pin(path) as held:
                if created_identity is not None and held[path][1] != created_identity:
                    raise EvidenceError("JOURNAL_REPLACED")
                self.check_path(path)
                if path.read_bytes() != raw:
                    raise EvidenceError("RUNNER_MANIFEST_READBACK_FAILED")
        except BaseException:
            self.failed = True
            raise

    def _writer_identity(self, stream):
        if self.security is None:
            return None
        import msvcrt
        return self.security.native.file_handle_info(msvcrt.get_osfhandle(stream.fileno()))[0]

    def _publish(self, record):
        try:
            with self.pin(self.root):
                self._publish_pinned(record)
        except BaseException:
            self.failed = True
            raise

    def _publish_pinned(self, record):
        body = record.model_dump(mode="json")
        raw = canonical({"record": body, "hash": digest("escryptorio:profile-journal:v1", body)})
        name = None
        try:
            self.check_path(self.root)
            with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as stream:
                name = stream.name
                created_identity = self._writer_identity(stream)
                if self.security is not None:
                    self.security.protect_new(Path(name))
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            self.check_path(Path(name))
            if self.path.exists():
                self.check_path(self.path)
            with self.pin(Path(name), allow_delete_files=True) as held:
                expected_identity = held.get(Path(name), (None, None))[1]
                if created_identity is not None and expected_identity != created_identity:
                    raise EvidenceError("JOURNAL_REPLACED")
                if self.security is not None and self._published_identity is not None:
                    self._read_current()
                os.replace(name, self.path)
                with self.pin(self.path) as published:
                    if expected_identity is not None and published[self.path][1] != expected_identity:
                        raise EvidenceError("JOURNAL_REPLACED")
                    self.check_path(self.path)
                    if read_record(self.path, record.operation_id, record.ownership_token) != record:
                        raise EvidenceError("JOURNAL_READBACK_FAILED")
                    info = self.path.stat()
                    published_id = published.get(self.path, (None, None))[1]
            self._published_identity = (info.st_dev, info.st_ino)
            self._published_file_id = published_id
        except BaseException:
            self.failed = True
            raise
        finally:
            if name is not None and Path(name).exists():
                self.check_path(Path(name))
                Path(name).unlink()

    def _read_current(self):
        with self.pin(self.path) as held:
            self.check_path(self.path)
            info = self.path.stat()
            if (info.st_dev, info.st_ino) != self._published_identity:
                raise EvidenceError("JOURNAL_REPLACED")
            if self._published_file_id is not None and held[self.path][1] != self._published_file_id:
                raise EvidenceError("JOURNAL_REPLACED")
            current = read_record(self.path, self.record.operation_id, self.record.ownership_token)
            if current != self.record:
                raise EvidenceError("JOURNAL_TRANSITION_INVALID")
            return current

    def transition(self, state, observed_sid=None, *, cleanup_result=None):
        with self._lock:
            if self.failed:
                raise EvidenceError("JOURNAL_REQUIRES_MANUAL_REVIEW")
            try:
                current = self._read_current()
            except BaseException:
                self.failed = True
                raise
            if state not in EDGES.get(current.state, set()):
                raise EvidenceError("JOURNAL_TRANSITION_INVALID")
            values = current.model_dump()
            values.update(state=state, generation=current.generation + 1,
                          observed_sid=observed_sid or current.observed_sid,
                          last_transition_ms=max(current.last_transition_ms, time.time_ns() // 1000000))
            candidate = Record(**values)
            if state in ("CREATED", "CLEANED") and candidate.observed_sid != candidate.expected_sid:
                raise EvidenceError("JOURNAL_OWNERSHIP_CONFLICT")
            if state == "CLEANED":
                from .rollback_verification import require_cleaned_result
                require_cleaned_result(cleanup_result, current)
            self._publish(candidate)
            self.record = candidate


def read_record(path, operation_id, ownership_token):
    path = Path(path)
    reject_redirects(path)
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
