"""Explicit atomic local export and strict database-independent verification."""
import hashlib
import os
import shutil
import tempfile
from itertools import islice
from pathlib import Path

from .core import EvidenceError, MAX_BYTES, canonical, package, report, strict_json

FILES = ("evidence.json", "report.json", "source.json")


def _bytes(value):
    data = canonical(value)
    if len(data) > MAX_BYTES:
        raise EvidenceError("SIZE_LIMIT")
    return data


def export_bundle(destination, pkg, rep, source):
    destination = Path(destination).absolute()
    parent = destination.parent
    if destination.exists() or destination.is_symlink() or not parent.is_dir() or any(p.is_symlink() for p in (parent, *parent.parents)):
        raise EvidenceError("EXPORT_PATH_INVALID")
    expected = package(source, pkg["mode"], pkg["as_of_ms"], pkg["captured_at_ms"])
    if canonical(pkg) != canonical(expected) or canonical(rep) != canonical(report(expected, source, rep["generated_at_ms"])):
        raise EvidenceError("EVIDENCE_HASH_MISMATCH")
    payloads = dict(zip(FILES, map(_bytes, (pkg, rep, source))))
    manifest = {"schema_version": 1, "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}}
    temporary = Path(tempfile.mkdtemp(prefix=".evidence-", dir=parent))
    try:
        for name, data in (*payloads.items(), ("manifest.json", _bytes(manifest))):
            with (temporary / name).open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        verify_bundle(temporary)
        if destination.exists() or destination.is_symlink():
            raise EvidenceError("EXPORT_PATH_INVALID")
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def verify_bundle(path):
    root = Path(path).absolute()
    if not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
        raise EvidenceError("EXPORT_MANIFEST_INVALID")
    entries = list(islice(root.iterdir(), 5))
    if {p.name for p in entries} != set(FILES) | {"manifest.json"} or len(entries) != 4:
        raise EvidenceError("EXPORT_MANIFEST_INVALID")
    raw = {}
    for entry in entries:
        if entry.is_symlink() or not entry.is_file() or entry.stat().st_size > MAX_BYTES:
            raise EvidenceError("EXPORT_MANIFEST_INVALID")
        with entry.open("rb") as handle:
            raw[entry.name] = handle.read(MAX_BYTES + 1)
        if len(raw[entry.name]) > MAX_BYTES:
            raise EvidenceError("SIZE_LIMIT")
    manifest = strict_json(raw["manifest.json"])
    if type(manifest) is not dict or set(manifest) != {"schema_version", "files"} or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or type(manifest["files"]) is not dict or set(manifest["files"]) != set(FILES):
        raise EvidenceError("EXPORT_MANIFEST_INVALID")
    if any(manifest["files"][name] != hashlib.sha256(raw[name]).hexdigest() for name in FILES):
        raise EvidenceError("EVIDENCE_HASH_MISMATCH")
    pkg, rep, source = (strict_json(raw[name]) for name in FILES)
    try:
        expected = package(source, pkg["mode"], pkg["as_of_ms"], pkg["captured_at_ms"])
        if canonical(pkg) != canonical(expected) or canonical(rep) != canonical(report(expected, source, rep["generated_at_ms"])):
            raise EvidenceError("EVIDENCE_HASH_MISMATCH")
    except (KeyError, TypeError):
        raise EvidenceError("SCHEMA_INVALID") from None
    return {"capture_id": pkg["capture_id"], "content_hash": pkg["content_hash"],
            "report_id": rep["report_id"], "report_content_hash": rep["report_content_hash"],
            "validation": pkg["validation"]}
