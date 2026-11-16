"""Read-back policy for a caller-owned disposable tree; no persistent setup.

This is a supervisor check, not an authorization source or protection from a
malicious process running as the supervisor. No profile API is used here.
"""
import ctypes as c
from contextlib import contextmanager
from pathlib import Path

from .windows_native import Native, SID_AND_ATTRIBUTES
from ..evidence.core import EvidenceError


def reject_redirects(path):
    """lstat also detects Windows junctions and other reparse tags, not just links."""
    path = Path(path)
    if (not path.is_absolute() or path.anchor.startswith("\\\\")
        or ".." in path.parts or ":" in str(path)[len(path.anchor):]):
        raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
    for entry in (path, *path.parents):
        info = entry.lstat()  # Missing/inaccessible paths fail closed.
        if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
    if path.resolve() != path:
        raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")


class WindowsJournalSecurity:
    """Only supervisor + SYSTEM full access; no package/broad ACEs accepted.

    Constructor and check are read-only. protect_new is only for newly-created
    empty children of the already-protected root. Callers create the root and
    its DACL explicitly in a synthetic fixture in this phase.
    """
    def __init__(self, root):
        self.root = Path(root)
        self.native = Native()
        reject_redirects(self.root)
        if not self.root.is_dir() or self.native.kernel.GetDriveTypeW(self.root.anchor) != 3:
            raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
        token = self.native.current_token()
        try:
            info = self.native.token_info(token, 1)
            self.owner = self.native.sid_text(c.cast(info, c.POINTER(SID_AND_ATTRIBUTES)).contents.Sid)
        finally:
            self.native.close(token)
        self.sddl = f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{self.owner})"
        self.identity = self._identity(self.root)
        self.native_identity = None
        self.check(self.root)

    @staticmethod
    def _identity(path):
        info = path.stat()
        return info.st_dev, info.st_ino

    def check(self, path):
        with self.pin(path):
            pass

    @contextmanager
    def pin(self, *paths, allow_delete_files=False):
        from .windows_paths import pinned_paths
        paths = tuple(Path(path) for path in paths)
        if any(not path.is_relative_to(self.root) for path in paths):
            raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
        with pinned_paths(self.native, paths, allow_delete_files=allow_delete_files) as held:
            root_identity = held[self.root][1]
            if self.native_identity is None:
                self.native_identity = root_identity
            if root_identity != self.native_identity or self._identity(self.root) != self.identity:
                raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
            for item, (handle, _) in held.items():
                if item.is_relative_to(self.root):
                    self._check_descriptor(item, handle)
            yield held
            for item, (handle, _) in held.items():
                if item.is_relative_to(self.root):
                    self._check_descriptor(item, handle)

    def _check_descriptor(self, path, handle=None):
        n = self.native
        attrs = (n.file_handle_info(handle)[1] if handle is not None
                 else n.kernel.GetFileAttributesW(str(path)))
        if attrs == 0xffffffff or attrs & 0x400:
            raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
        descriptor = n.handle_security(handle) if handle is not None else n.file_security(path, 5)
        owner, control = n.security_owner_control(descriptor)
        if owner != self.owner or not control & 0x1000:  # SE_DACL_PROTECTED
            raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
        entries = n.dacl_bytes(descriptor)
        if len(entries) != 2:
            raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
        trustees = set()
        for header, mask, sid in entries:
            # Only explicit ACCESS_ALLOWED_ACE; no inherited/object/callback ACE.
            if header[0] != 0 or header[1] != 3 or mask != 0x1f01ff:
                raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
            trustees.add(n.sid_text(c.create_string_buffer(sid)))
        if trustees != {self.owner, "S-1-5-18"}:
            raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")

    def protect_new(self, path):
        path = Path(path)
        self.check(path.parent)
        reject_redirects(path)
        if (not path.is_relative_to(self.root) or path == self.root
            or (path.is_dir() and any(path.iterdir()))
            or (path.is_file() and (path.stat().st_size or path.stat().st_nlink != 1))):
            raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
        self.native.apply_dacl(path, self.sddl)
        if path.is_dir():
            self.check(path)
        else:
            # The exclusive CRT writer is still open. A GENERIC_READ pin that
            # denies writes would conflict with our own writer. Verify its DACL
            # now; Journal compares the writer handle's File ID after close.
            reject_redirects(path)
            self._check_descriptor(path)


def validate_journal_preflight(journal):
    """Mandatory future native precondition. Legacy mock journals are insufficient."""
    try:
        if journal.security is None or journal.failed:
            raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED")
        journal.security.check(journal.path)
        journal.security.check(journal.root / "runner-request.json")
    except Exception:
        raise EvidenceError("JOURNAL_SECURITY_NOT_VERIFIED") from None
    return "JOURNAL_DACL_VERIFIED_WORKER_ACCESS_NOT_TESTED"
