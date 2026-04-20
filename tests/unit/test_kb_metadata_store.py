from __future__ import annotations

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
