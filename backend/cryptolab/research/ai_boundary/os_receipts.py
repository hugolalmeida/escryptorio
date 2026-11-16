"""Supervisor-owned observations over the existing Child/Job lifecycle.

No profile, process launcher, directory remover, or worker-data parser lives here.
Only the handles tracked by this operation are covered, never universal handles.
"""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import weakref
import threading

from .journal_security import reject_redirects
from .profile_journal import Record
from .rollback_verification import ResourceObservations
from .windows_paths import pinned_paths
from .windows_native import WindowsErrorCode
from ..evidence.core import EvidenceError

_CLAIMS = {}  # Process-local handle ownership, not an OS security boundary.
_CLAIMS_LOCK = threading.Lock()


def same_operation(left, right):
    return all(getattr(left, key) == getattr(right, key) for key in
               ("operation_id", "policy_id", "ownership_token", "expected_sid"))


class DirectoryScope:
    """Remember an exclusive fixture's identity and inspect only declared paths."""
    def __init__(self, native, root, relative_directories=()):
        self.native, self.root = native, Path(root)
        reject_redirects(self.root)
        if not self.root.is_dir():
            raise EvidenceError("TREE_IDENTITY_INVALID")
        paths = [self.root]
        for relative in relative_directories:
            value = Path(relative)
            if value.is_absolute() or ".." in value.parts or value == Path("."):
                raise EvidenceError("TREE_PATH_INVALID")
            path = self.root / value
            if not path.is_dir():
                raise EvidenceError("TREE_PATH_INVALID")
            paths.append(path)
        with pinned_paths(native, paths) as held:
            self.anchor_id = held[self.root.parent][1]
            self.identities = {path: held[path][1] for path in paths}

    def observe(self):
        states = {}
        try:
            with pinned_paths(self.native, [self.root.parent]) as held:
                if held[self.root.parent][1] != self.anchor_id:
                    return None, None
                for path, identity in self.identities.items():
                    try:
                        with pinned_paths(self.native, [path]) as observed:
                            if observed[path][1] != identity:
                                return None, None
                        states[path] = False
                    except FileNotFoundError:
                        states[path] = True
            return states[self.root], all(states.values())
        except (OSError, WindowsErrorCode, EvidenceError):
            return None, None  # Access error/redirection is never absence.


class OperationResources:
    """Bound to one operation and actual Child ownership, not callbacks/JSON."""
    def __init__(self, operation: Record, native, directory_scope: DirectoryScope):
        if type(operation) is not Record or directory_scope.native is not native:
            raise EvidenceError("RESOURCE_IDENTITY_INVALID")
        self.operation, self.native, self.directories = operation, native, directory_scope
        self.child = None
        self.job = None
        self.handles = {}
        self.streams = {}
        self.process_stopped = None
        self.exit_code = None
        self.active_processes = None
        self.job_empty = None
        self.errors = set()
        self._version = 0
        self._latest = None
        self._used = False
        self._sealed = False
        self._bridge = None
        self._created_sid = None
        self._delete_succeeded = None
        self._profile_source = None

    def _changed(self):
        self._version += 1
        self._latest = None

    def bind_child(self, child):
        if self._sealed or self.child is not None or child.native is not self.native or child.handles or child.streams:
            raise EvidenceError("RESOURCE_IDENTITY_INVALID")
        self.child = child

    def track(self, handle):
        with _CLAIMS_LOCK:
            if self._sealed:
                raise EvidenceError("RESOURCE_OPERATION_SEALED")
            owner = _CLAIMS.get(handle)
            if not handle or owner is not None and owner() is not self:
                raise EvidenceError("RESOURCE_OWNERSHIP_CONFLICT")
            if handle in self.handles and self.handles[handle] != "CLOSED":
                raise EvidenceError("RESOURCE_HANDLE_REUSE")
            _CLAIMS[handle] = weakref.ref(self)
            self.handles[handle] = "OPEN"
        self._changed()

    def own_job(self, job):
        if self.job is not None:
            raise EvidenceError("RESOURCE_JOB_REUSE")
        self.native.job_accounting(job)  # Real query, invalid/wrong type fails.
        self.track(job)
        self.job = job

    def closed(self, handle):
        with _CLAIMS_LOCK:
            if handle not in self.handles or _CLAIMS.get(handle, lambda: None)() is not self:
                raise EvidenceError("RESOURCE_OWNERSHIP_CONFLICT")
            self.handles[handle] = "CLOSED"
            _CLAIMS.pop(handle, None)
        self._changed()

    def close_failed(self, handle):
        self.errors.add("CloseHandle")
        if handle in self.handles:
            self.handles[handle] = "FAILED"
        self._changed()

    def transferred(self, handle, stream):
        if self.handles.get(handle) != "OPEN":
            raise EvidenceError("RESOURCE_OWNERSHIP_CONFLICT")
        self.handles[handle] = "CRT"
        self.streams[handle] = stream
        self._changed()

    def require_launch(self, root, job):
        if (Path(root) != self.directories.root or job != self.job or self.handles.get(job) != "OPEN"
            or self.directories.observe() != (False, False)):
            raise EvidenceError("RESOURCE_LAUNCH_IDENTITY_INVALID")

    def observe_process(self):
        child = self.child
        if child is None or child.process is None:
            return None
        if self.handles.get(child.process) == "CLOSED":
            return self.process_stopped  # Previously signalled termination is monotonic.
        if self.handles.get(child.process) != "OPEN":
            return None
        try:
            if self.job is None or self.handles.get(self.job) != "OPEN":
                return None
            member = w.BOOL()
            self.native.check(self.native.kernel.IsProcessInJob(child.process, self.job, c.byref(member)), "IsProcessInJob")
            if not member.value:
                raise EvidenceError("PROCESS_JOB_MISMATCH")
            state = self.native.kernel.WaitForSingleObject(child.process, 0)
            if state not in (0, 258):
                raise WindowsErrorCode("WaitForSingleObject")
            code = w.DWORD()
            self.native.check(self.native.kernel.GetExitCodeProcess(child.process, c.byref(code)), "GetExitCodeProcess")
            self.exit_code = code.value
            self.process_stopped = state == 0
            return self.process_stopped
        except (WindowsErrorCode, EvidenceError):
            self.errors.add("ProcessQuery")
            self.process_stopped = None
            self.exit_code = None
            return None

    def observe_job(self):
        if self.job is None:
            return None
        if self.handles.get(self.job) == "CLOSED":
            return self.job_empty
        try:
            self.active_processes = self.native.job_accounting(self.job).ActiveProcesses
            pids = self.native.job_pids(self.job)
            self.job_empty = self.active_processes == 0 and len(pids) == 0
            return self.job_empty
        except WindowsErrorCode:
            self.errors.add("JobQuery")
            self.job_empty = None
            self.active_processes = None
            return None

    def close_job(self):
        if self.job is None or self.handles.get(self.job) != "OPEN":
            raise EvidenceError("RESOURCE_JOB_INVALID")
        self.observe_job()
        try:
            self.native.close(self.job)
        except WindowsErrorCode:
            self.close_failed(self.job)
            raise
        self.closed(self.job)
        if self.job_empty is not True:
            self.job_empty = None  # Kill-on-close does not prove an empty Job.

    def handles_released(self):
        for handle, stream in self.streams.items():
            if self.handles.get(handle) == "CRT" and stream.closed:
                flags = w.DWORD()
                c.set_last_error(0)
                if not self.native.kernel.GetHandleInformation(handle, c.byref(flags)) and c.get_last_error() == 6:
                    self.closed(handle)
                else:
                    return None  # Possibly recycled handle; never close an unknown object.
        if "CloseHandle" in self.errors or "CloseStream" in self.errors:
            return False
        return all(state == "CLOSED" for state in self.handles.values()) if self.handles else None

    def collect(self, journal=None):
        if journal is not None and (journal.failed or not same_operation(self.operation, journal.record)):
            raise EvidenceError("RESOURCE_IDENTITY_INVALID")
        process, job = self.observe_process(), self.observe_job()
        released = self.handles_released()
        tree, directories = self.directories.observe()
        result = ResourceObservations(operation_id=self.operation.operation_id, policy_id=self.operation.policy_id,
            ownership_token=self.operation.ownership_token, expected_sid=self.operation.expected_sid,
            ownership_confirmed=True if self._created_sid == self.operation.expected_sid else None,
            delete_succeeded=self._delete_succeeded, process_stopped=process, job_empty=job,
            handles_released=released, operation_directories_absent=directories, tree_absent=tree,
            source="TESTED_MOCK" if self._profile_source == "TESTED_MOCK" else "SUPERVISOR_READ_ONLY")
        self._latest = (result, self._version, journal.record.generation if journal is not None else None)
        self._used = False
        return result

    def require_receipt(self, receipt, journal, *, consume=False):
        if (journal.failed or self._latest is None or self._used
            or receipt is not self._latest[0] or self._version != self._latest[1]
            or self._latest[2] != journal.record.generation
            or not same_operation(self.operation, journal.record) or not same_operation(receipt, journal.record)):
            raise EvidenceError("RESOURCE_RECEIPT_STALE_OR_FOREIGN")
        if consume:
            self._used = True
            self._sealed = True
