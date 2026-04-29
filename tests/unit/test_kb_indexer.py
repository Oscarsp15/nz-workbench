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
        self.chunker_ver: dict[tuple[str, str, str, str], int] = {}
        self._dbs: set[str] = set()

    def ensure_schema(self) -> None:
        return

    def get_body_sha256(self, key: ProcedureKey) -> str | None:
        return self.body_sha.get((key.database, key.schema, key.name, key.signature))

    def get_chunker_version(self, key: ProcedureKey) -> int | None:
        return self.chunker_ver.get((key.database, key.schema, key.name, key.signature))

    def get_last_altered(self, key: ProcedureKey) -> str | None:
        return self.last_alt.get((key.database, key.schema, key.name, key.signature))

    def upsert_procedure(
        self,
        key: ProcedureKey,
        last_altered: str,
        body_sha256: str,
        chunker_version: int = 0,
    ) -> None:
        self.body_sha[(key.database, key.schema, key.name, key.signature)] = body_sha256
        self.chunker_ver[(key.database, key.schema, key.name, key.signature)] = chunker_version
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
        self.get_ddl_batch_calls = 0

    def start(self) -> None:
        return

    def stop(self) -> None:
        return

    def call(self, tool: str, arguments: dict[str, Any]) -> ToolResult:  # noqa: PLR0911
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
        if tool == "nz_get_procedures_ddl_batch":
            self.get_ddl_batch_calls += 1
            if arguments.get("schema") == "DBO":
                return ToolResult(
                    ok=True,
                    result={
                        "procedures": [
                            {
                                "name": "SP1",
                                "ddl": "BEGIN\nSELECT 1;\nEND;\n",
                                "last_altered": "2026-01-01T00:00:00Z",
                                "size_bytes": 10,
                            }
                        ],
                        "count": 1,
                        "duration_ms": 10
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
    assert fake_client.get_ddl_batch_calls == 1

    r2 = indexer.bootstrap(["PROD_X"])
    assert r2.procedures_indexed == 0
    assert r2.procedures_skipped == 1
    assert fake_client.get_ddl_batch_calls == 2  # Fetched batch but skipped local indexing


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
    # Fake client returns size_bytes=10 → total is 10 bytes of work, not 1 proc.
    assert total_updates[-1]["total"] == 10

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
    assert done["work_units"] == 10

    # Second run: last_altered skip path still emits proc_start + proc_done(skipped).
    events.clear()
    indexer.bootstrap(["PROD_X"], on_progress=_on_progress)

    dones2 = [e for e in events if e["stage"] == "proc_done"]
    assert len(dones2) == 1
    assert dones2[0]["skipped"] is True
    assert dones2[0]["indexed"] is False
    assert dones2[0]["chunks"] == 0
    assert dones2[0]["work_units"] == 10


@pytest.mark.unit
def test_refresh_one_indexes_and_then_skips_by_body_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_meta = _FakeMetadataStore(tmp_path / "metadata.sqlite")
    fake_client = _FakeNzMcpClient(bin_path="nz-mcp")

    def _meta_factory(_p: Path) -> _FakeMetadataStore:
        return fake_meta

    def _chroma_factory(root: Path) -> _FakeChromaStore:
        return _FakeChromaStore(root)

    def _client_factory(*, bin_path: str) -> _FakeNzMcpClient:
        assert bin_path
        return fake_client

    monkeypatch.setattr(
        indexer,
        "load_config",
        lambda: _Cfg(state_dir=tmp_path, nz_mcp_bin="nz-mcp", embedder_model="BAAI/bge-m3"),
    )
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
    r1 = indexer.refresh_one("PROD_X", "DBO", "SP1", on_progress=events.append)

    assert r1.procedures_indexed == 1
    assert r1.procedures_skipped == 0
    assert r1.chunks_written == 1
    assert r1.errors == []

    stages = [e["stage"] for e in events]
    assert stages == ["total_update", "proc_start", "proc_done"]
    assert events[0] == {"stage": "total_update", "total": 1}
    assert events[-1]["indexed"] is True
    assert events[-1]["skipped"] is False
    assert events[-1]["error"] is None

    # Same body hash on second run → indexed=0, skipped=1.
    events.clear()
    r2 = indexer.refresh_one("PROD_X", "DBO", "SP1", on_progress=events.append)
    assert r2.procedures_indexed == 0
    assert r2.procedures_skipped == 1
    assert r2.errors == []
    last_event = events[-1]
    assert last_event["skipped"] is True
    assert last_event["indexed"] is not True


@pytest.mark.unit
def test_bootstrap_invalidates_skip_when_chunker_version_drifts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Bootstrap must NOT rely on last_altered alone when chunker_version drifted.

    Before the fix, a stale ``chunker_version`` was ignored by bootstrap's
    early-skip (``last_altered`` match was enough). Users whose SPs weren't
    altered in Netezza never got their local index refreshed after a chunker
    bump — defeating the auto-migration.
    """

    fake_meta = _FakeMetadataStore(tmp_path / "metadata.sqlite")
    fake_client = _FakeNzMcpClient(bin_path="nz-mcp")

    def _meta_factory(_p: Path) -> _FakeMetadataStore:
        return fake_meta

    def _chroma_factory(root: Path) -> _FakeChromaStore:
        return _FakeChromaStore(root)

    def _client_factory(*, bin_path: str) -> _FakeNzMcpClient:
        assert bin_path
        return fake_client

    monkeypatch.setattr(
        indexer,
        "load_config",
        lambda: _Cfg(state_dir=tmp_path, nz_mcp_bin="nz-mcp", embedder_model="BAAI/bge-m3"),
    )
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

    # First bootstrap at the current chunker version indexes normally.
    r1 = indexer.bootstrap(["PROD_X"])
    assert r1.procedures_indexed == 1
    assert fake_client.get_ddl_batch_calls == 1

    # Simulate a legacy index (chunker v0) while last_altered still matches PROD.
    key = ProcedureKey(database="PROD_X", schema="DBO", name="SP1", signature="()")
    fake_meta.chunker_ver[(key.database, key.schema, key.name, key.signature)] = 0

    # Second bootstrap: last_altered matches but chunker_version differs → re-index.
    r2 = indexer.bootstrap(["PROD_X"])
    assert r2.procedures_indexed == 1, "chunker_version drift must invalidate bootstrap skip"
    assert r2.procedures_skipped == 0
    assert fake_client.get_ddl_batch_calls == 2


@pytest.mark.unit
def test_refresh_one_reindexes_when_chunker_version_drifts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Same DDL body + older chunker_version → re-index (not skipped).

    Simulates a stored-state migration: user ran bootstrap with chunker v0
    (pre-versioning), we bumped the chunker, next refresh must re-chunk the
    same body even though its ``body_sha256`` matches.
    """

    fake_meta = _FakeMetadataStore(tmp_path / "metadata.sqlite")
    fake_client = _FakeNzMcpClient(bin_path="nz-mcp")

    def _meta_factory(_p: Path) -> _FakeMetadataStore:
        return fake_meta

    def _chroma_factory(root: Path) -> _FakeChromaStore:
        return _FakeChromaStore(root)

    def _client_factory(*, bin_path: str) -> _FakeNzMcpClient:
        assert bin_path
        return fake_client

    monkeypatch.setattr(
        indexer,
        "load_config",
        lambda: _Cfg(state_dir=tmp_path, nz_mcp_bin="nz-mcp", embedder_model="BAAI/bge-m3"),
    )
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

    # First pass indexes at the current chunker version.
    r1 = indexer.refresh_one("PROD_X", "DBO", "SP1")
    assert r1.procedures_indexed == 1
    assert fake_client.get_ddl_calls == 1

    # Simulate an older chunker having indexed this row (e.g. pre-migration).
    key = ProcedureKey(database="PROD_X", schema="DBO", name="SP1", signature="()")
    fake_meta.chunker_ver[(key.database, key.schema, key.name, key.signature)] = 0

    # Second pass: body hash still matches but chunker_version drifted → re-index.
    r2 = indexer.refresh_one("PROD_X", "DBO", "SP1")
    assert r2.procedures_indexed == 1, "stale chunker_version must trigger re-index"
    assert r2.procedures_skipped == 0
    assert fake_client.get_ddl_calls == 2


@pytest.mark.unit
def test_refresh_one_surfaces_ddl_fetch_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_meta = _FakeMetadataStore(tmp_path / "metadata.sqlite")

    class _FailingClient(_FakeNzMcpClient):
        def call(self, tool: str, arguments: dict[str, Any]) -> ToolResult:
            if tool == "nz_get_procedure_ddl":
                return ToolResult(
                    ok=False,
                    result=None,
                    error_code="NOT_FOUND",
                    error_context={"procedure": arguments.get("procedure")},
                )
            return super().call(tool, arguments)

    fake_client = _FailingClient(bin_path="nz-mcp")

    def _meta_factory(_p: Path) -> _FakeMetadataStore:
        return fake_meta

    def _chroma_factory(root: Path) -> _FakeChromaStore:
        return _FakeChromaStore(root)

    def _client_factory(*, bin_path: str) -> _FailingClient:
        assert bin_path
        return fake_client

    monkeypatch.setattr(
        indexer,
        "load_config",
        lambda: _Cfg(state_dir=tmp_path, nz_mcp_bin="nz-mcp", embedder_model="BAAI/bge-m3"),
    )
    monkeypatch.setattr(indexer, "MetadataStore", _meta_factory)
    monkeypatch.setattr(indexer, "ChromaStore", _chroma_factory)
    monkeypatch.setattr(indexer, "NzMcpClient", _client_factory)
    monkeypatch.setattr(indexer, "make_embedder", lambda _name: _FakeEmbedder())

    events: list[dict[str, Any]] = []
    r = indexer.refresh_one("PROD_X", "DBO", "MISSING_SP", on_progress=events.append)

    assert r.procedures_indexed == 0
    assert r.procedures_skipped == 0
    assert r.errors and "MISSING_SP" in r.errors[0]

    done = [e for e in events if e["stage"] == "proc_done"][-1]
    assert done["error"] is not None
    assert done["indexed"] is False
    assert done["skipped"] is False


@pytest.mark.unit
def test_bootstrap_uses_batch_ddl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_meta = _FakeMetadataStore(tmp_path / "metadata.sqlite")
    fake_client = _FakeNzMcpClient(bin_path="nz-mcp")

    def _meta_factory(_p: Path) -> _FakeMetadataStore:
        return fake_meta

    def _chroma_factory(root: Path) -> _FakeChromaStore:
        return _FakeChromaStore(root)

    def _client_factory(*, bin_path: str) -> _FakeNzMcpClient:
        return fake_client

    monkeypatch.setattr(
        indexer,
        "load_config",
        lambda: _Cfg(state_dir=tmp_path, nz_mcp_bin="nz-mcp", embedder_model="BAAI/bge-m3"),
    )
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

    r1 = indexer.bootstrap(["PROD_X"])
    assert r1.procedures_indexed == 1
    assert r1.errors == []
    assert fake_client.get_ddl_batch_calls == 1
    assert fake_client.get_ddl_calls == 0


@pytest.mark.unit
def test_bootstrap_fallback_to_individual_ddl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_meta = _FakeMetadataStore(tmp_path / "metadata.sqlite")
    fake_client = _FakeNzMcpClient(bin_path="nz-mcp")

    # Force batch to fail with UNKNOWN_TOOL
    original_call = fake_client.call
    def fallback_call(tool: str, arguments: dict[str, Any]) -> ToolResult:
        if tool == "nz_get_procedures_ddl_batch":
            return ToolResult(
                ok=False,
                result=None,
                error_code="UNKNOWN_TOOL",
                error_context={"tool": tool},
            )
        return original_call(tool, arguments)

    fake_client.call = fallback_call  # type: ignore

    def _meta_factory(_p: Path) -> _FakeMetadataStore:
        return fake_meta

    def _chroma_factory(root: Path) -> _FakeChromaStore:
        return _FakeChromaStore(root)

    def _client_factory(*, bin_path: str) -> _FakeNzMcpClient:
        return fake_client

    monkeypatch.setattr(
        indexer,
        "load_config",
        lambda: _Cfg(state_dir=tmp_path, nz_mcp_bin="nz-mcp", embedder_model="BAAI/bge-m3"),
    )
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

    r1 = indexer.bootstrap(["PROD_X"])
    assert r1.procedures_indexed == 1
    assert r1.errors == []
    # Individual fetch is used
    assert fake_client.get_ddl_calls == 1

