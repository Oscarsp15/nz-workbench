from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from nz_workbench.kb.metadata_store import MetadataStore, ProcedureKey, Reference


@pytest.mark.unit
def test_metadata_store_roundtrip(tmp_path: Path) -> None:
    store = MetadataStore(tmp_path / "metadata.sqlite")
    store.ensure_schema()

    key = ProcedureKey(database="PROD_X", schema="DBO", name="SP1", signature="()")
    store.upsert_procedure(key, last_altered="2026-01-01T00:00:00Z", body_sha256="abc")
    store.upsert_references(
        key,
        [
            Reference(
                kind="write",
                op="INSERT",
                ref_database="PROD_X",
                ref_schema="DBO",
                ref_object="T1",
                line_from=1,
                line_to=2,
            ),
            Reference(
                kind="call",
                op="CALL",
                ref_database=None,
                ref_schema="DBO",
                ref_object="SP2",
                line_from=None,
                line_to=None,
            ),
        ],
    )

    assert store.get_body_sha256(key) == "abc"
    assert store.get_last_altered(key) == "2026-01-01T00:00:00Z"
    assert store.list_indexed_databases() == ["PROD_X"]

    writers = store.procedures_writing_to("T1")
    assert writers == [key]

    callers = store.procedures_calling("DBO", "SP2")
    assert callers == [key]


@pytest.mark.unit
def test_metadata_store_persists_chunker_version(tmp_path: Path) -> None:
    """``get_chunker_version`` returns the value passed to ``upsert_procedure``."""

    store = MetadataStore(tmp_path / "metadata.sqlite")
    store.ensure_schema()

    key = ProcedureKey(database="PROD_X", schema="DBO", name="SP_V", signature="()")
    store.upsert_procedure(
        key,
        last_altered="2026-01-01T00:00:00Z",
        body_sha256="hash-xyz",
        chunker_version=3,
    )

    assert store.get_chunker_version(key) == 3

    # Missing procedure returns None.
    other = ProcedureKey(database="OTHER", schema="X", name="Y", signature="()")
    assert store.get_chunker_version(other) is None


@pytest.mark.unit
def test_metadata_store_migrates_legacy_db_without_chunker_version(tmp_path: Path) -> None:
    """Older DBs (pre-versioning) must get the column added on ``ensure_schema``."""

    path = tmp_path / "legacy.sqlite"
    # Build a legacy schema: procedure table without chunker_version.
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE procedure (
                database       TEXT NOT NULL,
                schema         TEXT NOT NULL,
                name           TEXT NOT NULL,
                signature      TEXT NOT NULL,
                last_altered   TEXT,
                body_sha256    TEXT,
                indexed_at     TEXT NOT NULL,
                PRIMARY KEY (database, schema, name, signature)
            );
            """
        )
        conn.execute(
            "INSERT INTO procedure VALUES (?, ?, ?, ?, ?, ?, ?);",
            (
                "PROD_X",
                "DBO",
                "OLD_SP",
                "()",
                "2020-01-01T00:00:00Z",
                "oldhash",
                "2020-01-02T00:00:00Z",
            ),
        )

    store = MetadataStore(path)
    store.ensure_schema()

    key = ProcedureKey(database="PROD_X", schema="DBO", name="OLD_SP", signature="()")
    # Column exists and defaults to 0 (pre-versioning marker).
    assert store.get_chunker_version(key) == 0
    # Existing row wasn't clobbered.
    assert store.get_body_sha256(key) == "oldhash"
