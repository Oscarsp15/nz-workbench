from __future__ import annotations

from pathlib import Path

import pytest

from nz_workbench.kb.chroma_store import ChromaStore


@pytest.mark.unit
def test_chroma_store_upsert_search_delete(tmp_path: Path) -> None:
    store = ChromaStore(tmp_path)
    store.upsert(
        ids=["1", "2"],
        vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        metadatas=[
            {
                "database": "PROD_X",
                "schema": "DBO",
                "procedure": "SP1",
                "line_from": 1,
                "line_to": 2,
            },
            {
                "database": "PROD_Y",
                "schema": "DBO",
                "procedure": "SP2",
                "line_from": 3,
                "line_to": 4,
            },
        ],
        documents=["alpha", "beta"],
    )

    hits = store.search_semantic([1.0, 0.0, 0.0], k=2)
    assert hits
    assert hits[0].procedure in {"SP1", "SP2"}

    hits_filtered = store.search_semantic([1.0, 0.0, 0.0], k=10, filters={"database": "PROD_X"})
    assert all(h.database == "PROD_X" for h in hits_filtered)

    store.delete_by_procedure("PROD_X", "DBO", "SP1")
    hits_after = store.search_semantic([1.0, 0.0, 0.0], k=10, filters={"database": "PROD_X"})
    assert hits_after == []
