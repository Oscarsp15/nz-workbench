from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from nz_workbench.kb import indexer
from nz_workbench.kb.metadata_store import ProcedureKey
from nz_workbench.nz_mcp_client import ToolResult


@dataclass
class _Cfg:
    state_dir: Path
    nz_mcp_bin: str
    embedder_model: str


class _FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0, 0.0] for _ in texts]


class _FakeChromaStore:
    def __init__(self, root: Path) -> None:
        self.root: Path = root
        self.upserts: list[tuple[list[str], list[dict[str, Any]]]] = []
        self.deletes: list[tuple[str, str, str]] = []

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str],
    ) -> None:
        self.upserts.append((ids, metadatas))

    def delete_by_procedure(self, database: str, schema: str, procedure: str) -> None:
        self.deletes.append((database, schema, procedure))


class _FakeMetadataStore:
    def __init__(self, path: Path) -> None:
        self.path: Path = path
        self.body_sha: dict[tuple[str, str, str, str], str] = {}
        self.last_alt: dict[tuple[str, str, str, str], str] = {}
        self._dbs: set[str] = set()

    def ensure_schema(self) -> None:
        return

    def get_body_sha256(self, key: ProcedureKey) -> str | None:
        return self.body_sha.get((key.database, key.schema, key.name, key.signature))

    def get_last_altered(self, key: ProcedureKey) -> str | None:
        return self.last_alt.get((key.database, key.schema, key.name, key.signature))

    def upsert_procedure(self, key: ProcedureKey, last_altered: str, body_sha256: str) -> None:
        self.body_sha[(key.database, key.schema, key.name, key.signature)] = body_sha256
        if last_altered:
            self.last_alt[(key.database, key.schema, key.name, key.signature)] = last_altered
        self._dbs.add(key.database)

    def upsert_references(self, key: ProcedureKey, references: list[Any]) -> None:
        return

    def list_indexed_databases(self) -> list[str]:
        return sorted(self._dbs)


class _FakeNzMcpClient:
    def __init__(self, bin_path: str) -> None:
        self.bin_path = bin_path
        self.get_ddl_calls = 0

    def start(self) -> None:
        return

    def stop(self) -> None:
        return

    def call(self, tool: str, arguments: dict[str, Any]) -> ToolResult:
        if tool == "nz_list_schemas":
            return ToolResult(
                ok=True,
                result={"schemas": [{"name": "DBO"}]},
                error_code=None,
                error_context=None,
            )
        if tool == "nz_list_procedures":
            if "schema" not in arguments:
                return ToolResult(
                    ok=False,
                    result=None,
                    error_code="INVALID_INPUT",
                    error_context={"detail": "schema required"},
                )
            return ToolResult(
                ok=True,
                result={
                    "procedures": [
                        {
                            "name": "SP1",
                            "arguments": "()",
                            "last_altered": "2026-01-01T00:00:00Z",
                            "size_bytes": 10,
                        }
                    ]
                },
                error_code=None,
                error_context=None,
            )
        if tool == "nz_get_procedure_ddl":
            self.get_ddl_calls += 1
            return ToolResult(
                ok=True,
                result={"ddl": "BEGIN\nSELECT 1;\nEND;\n"},
                error_code=None,
                error_context=None,
            )
        if tool == "nz_analyze_procedure_references":
            return ToolResult(
                ok=True,
                result={
                    "references": [
                        {
                            "kind": "read",
                            "op": "SELECT",
                            "ref_database": None,
                            "ref_schema": "DBO",
                            "ref_object": "T",
                            "line_from": 1,
                            "line_to": 1,
                        }
                    ]
                },
                error_code=None,
                error_context=None,
            )
        return ToolResult(
            ok=False,
            result=None,
            error_code="UNKNOWN_TOOL",
            error_context={"tool": tool, "arguments": arguments},
        )


@pytest.mark.unit
def test_bootstrap_indexes_and_skips_by_last_altered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_meta = _FakeMetadataStore(tmp_path / "metadata.sqlite")
    fake_client = _FakeNzMcpClient(bin_path="nz-mcp")

    def meta_factory(_path: Path) -> _FakeMetadataStore:
        return fake_meta

    def chroma_factory(root: Path) -> _FakeChromaStore:
        return _FakeChromaStore(root)

    def client_factory(*, bin_path: str) -> _FakeNzMcpClient:
        assert bin_path
        return fake_client

    monkeypatch.setattr(
        indexer,
        "load_config",
        lambda: _Cfg(state_dir=tmp_path, nz_mcp_bin="nz-mcp", embedder_model="BAAI/bge-m3"),
    )
    monkeypatch.setattr(indexer, "MetadataStore", meta_factory)
    monkeypatch.setattr(indexer, "ChromaStore", chroma_factory)
    monkeypatch.setattr(indexer, "NzMcpClient", client_factory)
    monkeypatch.setattr(indexer, "make_embedder", lambda _name: _FakeEmbedder())
    monkeypatch.setattr(
        indexer,
        "chunk",
        lambda _ddl: [
            type("C", (), {"text": "x", "line_from": 1, "line_to": 1, "section_hint": "body"})()
        ],
    )

    r1 = indexer.bootstrap(["PROD_X"])
    assert r1.procedures_indexed == 1
    assert r1.errors == []
    assert fake_client.get_ddl_calls == 1

    r2 = indexer.bootstrap(["PROD_X"])
    assert r2.procedures_indexed == 0
    assert r2.procedures_skipped == 1
    assert fake_client.get_ddl_calls == 1  # last_altered skip avoids re-fetching DDL


@pytest.mark.unit
def test_bootstrap_emits_progress_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_meta = _FakeMetadataStore(tmp_path / "metadata.sqlite")
    fake_client = _FakeNzMcpClient(bin_path="nz-mcp")

    monkeypatch.setattr(
        indexer,
        "load_config",
        lambda: _Cfg(state_dir=tmp_path, nz_mcp_bin="nz-mcp", embedder_model="BAAI/bge-m3"),
    )

    def _meta_factory(_p: Path) -> _FakeMetadataStore:
        return fake_meta

    def _chroma_factory(root: Path) -> _FakeChromaStore:
        return _FakeChromaStore(root)

    def _client_factory(*, bin_path: str) -> _FakeNzMcpClient:
        assert bin_path
        return fake_client

    monkeypatch.setattr(indexer, "MetadataStore", _meta_factory)
    monkeypatch.setattr(indexer, "ChromaStore", _chroma_factory)
    monkeypatch.setattr(indexer, "NzMcpClient", _client_factory)
    monkeypatch.setattr(indexer, "make_embedder", lambda _name: _FakeEmbedder())
    monkeypatch.setattr(
        indexer,
        "chunk",
        lambda _ddl: [
            type("C", (), {"text": "x", "line_from": 1, "line_to": 1, "section_hint": "body"})()
        ],
    )

    events: list[dict[str, Any]] = []

    def _on_progress(event: dict[str, Any]) -> None:
        events.append(event)

    indexer.bootstrap(["PROD_X"], on_progress=_on_progress)

    stages = [e["stage"] for e in events]
    assert "total_update" in stages
    assert "proc_start" in stages
    assert "proc_done" in stages

    total_updates = [e for e in events if e["stage"] == "total_update"]
    assert total_updates[-1]["total"] == 1

    starts = [e for e in events if e["stage"] == "proc_start"]
    assert starts == [{"stage": "proc_start", "database": "PROD_X", "schema": "DBO", "name": "SP1"}]

    dones = [e for e in events if e["stage"] == "proc_done"]
    assert len(dones) == 1
    done = dones[0]
    assert done["database"] == "PROD_X"
    assert done["schema"] == "DBO"
    assert done["name"] == "SP1"
    assert done["indexed"] is True
    assert done["skipped"] is False
    assert done["error"] is None
    assert done["chunks"] == 1

    # Second run: last_altered skip path still emits proc_start + proc_done(skipped).
    events.clear()
    indexer.bootstrap(["PROD_X"], on_progress=_on_progress)

    dones2 = [e for e in events if e["stage"] == "proc_done"]
    assert len(dones2) == 1
    assert dones2[0]["skipped"] is True
    assert dones2[0]["indexed"] is False
    assert dones2[0]["chunks"] == 0
