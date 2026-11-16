"""Bound metadata handles for known paths; never creates or deletes objects."""
from contextlib import contextmanager
from pathlib import Path

from .journal_security import reject_redirects
from ..evidence.core import EvidenceError


@contextmanager
def pinned_paths(native, paths, *, allow_delete_files=False):
    """Pin ancestors before children. Sharing violations fail closed.

    A publication source explicitly allows delete sharing for atomic replace.
    Such a file can be renamed: callers must compare its held File ID with the
    published target. This does not defend against all same-user/kernel attacks.
    """
    paths = tuple(Path(path) for path in paths)
    entries = set()
    for path in paths:
        if not path.is_absolute() or path.anchor.startswith("\\\\") or ".." in path.parts:
            raise EvidenceError("PATH_IDENTITY_NOT_VERIFIED")
        entries.update((path, *path.parents))
    handles, result = [], {}
    try:
        for path in sorted(entries, key=lambda item: (len(item.parts), str(item).casefold())):
            reject_redirects(path)
            directory = path.is_dir()
            handle = native.metadata_handle(path, directory=directory,
                                            allow_delete=allow_delete_files and not directory)
            handles.append(handle)
            identity, attributes, links = native.file_handle_info(handle)
            final = native.final_path(handle)
            if final.startswith("\\\\?\\"):
                final = final[4:]
            if (Path(final) != path or attributes & 0x400 or bool(attributes & 0x10) != directory
                or not directory and links != 1):
                raise EvidenceError("PATH_IDENTITY_NOT_VERIFIED")
            result[path] = (handle, identity)
        yield result
        for path, (handle, identity) in result.items():
            current, attributes, _ = native.file_handle_info(handle)
            final = native.final_path(handle)
            if final.startswith("\\\\?\\"):
                final = final[4:]
            # An allowed publication source may have moved to journal.json.
            if (current != identity or attributes & 0x400
                or (attributes & 0x10 or not allow_delete_files) and Path(final) != path):
                raise EvidenceError("PATH_IDENTITY_CHANGED")
    finally:
        failures = []
        for handle in reversed(handles):
            try:
                native.close(handle)
            except Exception:
                failures.append(handle)
        if failures:
            raise EvidenceError("ROLLBACK_INCOMPLETE")
