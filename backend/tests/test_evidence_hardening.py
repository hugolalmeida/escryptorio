"""Adversarial, synthetic input for the read-only evidence foundation."""
import sqlite3

import pytest

from cryptolab.research.evidence.core import EvidenceError, canonical, source_from_db, strict_json


@pytest.mark.parametrize("payload,manifest", [(None, "{}"), ("{}", None), (b"{}", "{}"), ("{}", b"{}"), (42, "{}")])
def test_database_bad_types_fail_closed(tmp_path, payload, manifest):
    path = tmp_path / "source.db"
    identifier = "a" * 64
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE historical_datasets(id TEXT,payload,manifest)")
        db.execute("INSERT INTO historical_datasets VALUES (?,?,?)", (identifier, payload, manifest))
    with pytest.raises(EvidenceError, match="SOURCE_UNVERIFIED"):
        source_from_db(path, identifier)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT payload,manifest FROM historical_datasets").fetchone() == (payload, manifest)


def test_absent_database_and_missing_schema_are_controlled(tmp_path):
    with pytest.raises(EvidenceError, match="SOURCE_UNAVAILABLE"):
        source_from_db(tmp_path / "missing", "a" * 64)
    path = tmp_path / "empty"
    sqlite3.connect(path).close()
    with pytest.raises(EvidenceError, match="SOURCE_UNAVAILABLE"):
        source_from_db(path, "a" * 64)


def test_depth_is_bounded_and_bad_unicode_is_controlled():
    nested = 0
    for _ in range(70): nested = [nested]
    with pytest.raises(EvidenceError, match="SCHEMA_INVALID"): canonical(nested)
    with pytest.raises(EvidenceError, match="SCHEMA_INVALID"): canonical("\ud800")
    with pytest.raises(EvidenceError, match="SCHEMA_INVALID"): strict_json(b'[' * 1100 + b'0' + b']' * 1100)
