"""Bootstrap and incremental indexing of production procedures into the KB."""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import structlog

from nz_workbench.config import load_config
from nz_workbench.kb.chroma_store import ChromaStore
from nz_workbench.kb.chunker import CHUNKER_VERSION, chunk
from nz_workbench.kb.embedder import Embedder, make_embedder
from nz_workbench.kb.metadata_store import MetadataStore, ProcedureKey, Reference
from nz_workbench.nz_mcp_client import NzMcpClient, ToolResult

_log = structlog.get_logger(__name__)

_TOOL_LIST_PROCS: Final[str] = "nz_list_procedures"
_TOOL_GET_DDL: Final[str] = "nz_get_procedure_ddl"
_TOOL_LIST_SCHEMAS: Final[str] = "nz_list_schemas"
_QUAL_DB_SCHEMA_OBJ: Final[int] = 3
_QUAL_SCHEMA_OBJ: Final[int] = 2


ProgressEvent = dict[str, Any]
"""Event payload passed to ``on_progress`` callbacks.

Shapes (``stage`` is always present):

- ``{"stage": "total_update", "total": int}`` — total work units discovered so
  far. Work units default to the sum of ``size_bytes`` across procedures so
  that a huge SP advances the bar proportionally; when size is missing each
  proc counts as ``1`` (falls back to count-based progress).
- ``{"stage": "proc_start", "database": str, "schema": str, "name": str}``.
- ``{"stage": "proc_done", "database": str, "schema": str, "name": str,
     "chunks": int, "indexed": bool, "skipped": bool, "error": str | None,
     "work_units": int}``. ``work_units`` is the size that should advance the
  bar for this procedure.
"""


def _work_units(proc: _ProcInfo) -> int:
    """How much progress this procedure contributes.

    Use ``size_bytes`` when known so the bar advances by bytes (stable ETA for
    mixed procedure sizes); fall back to ``1`` so progress remains count-based
    if nz-mcp doesn't return sizes.
    """

    return proc.size_bytes if proc.size_bytes and proc.size_bytes > 0 else 1


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass(frozen=True, slots=True)
class IndexReport:
    """Result of an indexing pass."""

    procedures_indexed: int
    procedures_skipped: int
    chunks_written: int
    duration_seconds: float
    errors: list[str]


@dataclass(frozen=True, slots=True)
class _ProcInfo:
    database: str
    schema: str
    name: str
    signature: str
    last_altered: str
    size_bytes: int | None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tool_ok(res: ToolResult) -> bool:
    return bool(res.ok and isinstance(res.result, dict))


def _extract_list(res: ToolResult, *, key: str) -> list[dict[str, Any]]:
    if not _tool_ok(res) or res.result is None:
        return []
    payload = res.result.get(key)
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(res.result.get("result"), list):
        return [x for x in res.result["result"] if isinstance(x, dict)]
    return []


def _extract_text(res: ToolResult, *, keys: tuple[str, ...]) -> str | None:
    if not _tool_ok(res) or res.result is None:
        return None
    for k in keys:
        value = res.result.get(k)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _parse_proc_list(database: str, schema: str, raw: list[dict[str, Any]]) -> list[_ProcInfo]:
    procs: list[_ProcInfo] = []
    for item in raw:
        name = str(item.get("name") or item.get("procedure") or item.get("proc_name") or "").strip()
        if not name:
            continue
        signature = str(
            item.get("arguments")
            or item.get("signature")
            or item.get("args")
            or item.get("parameters")
            or "()"
        )
        last_altered = str(
            item.get("last_altered") or item.get("lastaltertime") or item.get("lastAlterTime") or ""
        )
        size_raw = item.get("size_bytes") or item.get("size") or item.get("bytes")
        size_bytes = int(size_raw) if isinstance(size_raw, int) else None
        procs.append(
            _ProcInfo(
                database=database,
                schema=schema,
                name=name,
                signature=signature,
                last_altered=last_altered,
                size_bytes=size_bytes,
            )
        )
    return procs


def _list_schema_names(client: NzMcpClient, database: str) -> tuple[list[str], str | None]:
    schemas_res = _call_with_fallbacks(
        client,
        _TOOL_LIST_SCHEMAS,
        [{"database": database}, {"db": database}],
    )
    if not _tool_ok(schemas_res):
        return [], f"failed to list schemas for {database}: {schemas_res.error_code}"

    schema_items = _extract_list(schemas_res, key="schemas")
    if not schema_items and schemas_res.result is not None:
        maybe = schemas_res.result.get("items") or schemas_res.result.get("schemas")
        if isinstance(maybe, list):
            schema_items = [x for x in maybe if isinstance(x, dict)]

    schema_names = [
        str(s.get("name") or s.get("schema") or s.get("schema_name") or "").strip()
        for s in schema_items
    ]
    schema_names = [s for s in schema_names if s]
    if not schema_names:
        return [], f"list schemas returned empty for {database}"
    return schema_names, None


def _list_procedures_in_schema(
    client: NzMcpClient, database: str, schema: str
) -> tuple[list[_ProcInfo], str | None]:
    procs_res = _call_with_fallbacks(
        client,
        _TOOL_LIST_PROCS,
        [
            {"database": database, "schema": schema},
            {"database": database, "schema": schema, "pattern": None},
            {"db": database, "schema": schema},
        ],
    )
    if not _tool_ok(procs_res):
        return [], f"failed to list procedures for {database}.{schema}: {procs_res.error_code}"

    raw = _extract_list(procs_res, key="procedures")
    if not raw and procs_res.result is not None:
        maybe = procs_res.result.get("items") or procs_res.result.get("procedures")
        if isinstance(maybe, list):
            raw = [x for x in maybe if isinstance(x, dict)]

    return _parse_proc_list(database, schema, raw), None


def _index_procedures(
    *,
    procs: list[_ProcInfo],
    client: NzMcpClient,
    chroma: ChromaStore,
    metadata: MetadataStore,
    embedder: Embedder,
    on_progress: ProgressCallback | None = None,
) -> tuple[int, int, int, list[str]]:
    indexed = 0
    skipped = 0
    chunks_written = 0
    errors: list[str] = []

    for proc in procs:
        key = ProcedureKey(
            database=proc.database,
            schema=proc.schema,
            name=proc.name,
            signature=proc.signature,
        )
        work_units = _work_units(proc)
        if on_progress is not None:
            on_progress(
                {
                    "stage": "proc_start",
                    "database": proc.database,
                    "schema": proc.schema,
                    "name": proc.name,
                }
            )

        if proc.last_altered:
            prev_last = metadata.get_last_altered(key)
            prev_chunker = metadata.get_chunker_version(key)
            # Skip only when BOTH the source hasn't changed AND the chunker
            # version matches. A chunker bump invalidates the local index,
            # so we must fall through to ``_index_one`` for a fresh pass.
            if (
                prev_last is not None
                and prev_last == proc.last_altered
                and prev_chunker == CHUNKER_VERSION
            ):
                skipped += 1
                if on_progress is not None:
                    on_progress(
                        {
                            "stage": "proc_done",
                            "database": proc.database,
                            "schema": proc.schema,
                            "name": proc.name,
                            "chunks": 0,
                            "indexed": False,
                            "skipped": True,
                            "error": None,
                            "work_units": work_units,
                        }
                    )
                continue

        _log.info(
            "kb_index_proc_start",
            database=proc.database,
            schema=proc.schema,
            procedure=proc.name,
        )
        did_index, chunks, err = _index_one(
            client=client,
            chroma=chroma,
            metadata=metadata,
            embedder=embedder,
            proc=proc,
        )
        if err is not None:
            errors.append(err)
            _log.error("kb_index_proc_failed", error=err)
            if on_progress is not None:
                on_progress(
                    {
                        "stage": "proc_done",
                        "database": proc.database,
                        "schema": proc.schema,
                        "name": proc.name,
                        "chunks": 0,
                        "indexed": False,
                        "skipped": False,
                        "error": err,
                        "work_units": work_units,
                    }
                )
            continue

        is_skipped = did_index == 0
        if is_skipped:
            skipped += 1
        else:
            indexed += 1
            chunks_written += chunks

        _log.info(
            "kb_index_proc_done",
            database=proc.database,
            schema=proc.schema,
            procedure=proc.name,
            chunks=chunks,
            indexed=bool(did_index),
        )
        if on_progress is not None:
            on_progress(
                {
                    "stage": "proc_done",
                    "database": proc.database,
                    "schema": proc.schema,
                    "name": proc.name,
                    "chunks": chunks,
                    "indexed": bool(did_index),
                    "skipped": is_skipped,
                    "error": None,
                    "work_units": work_units,
                }
            )

    return indexed, skipped, chunks_written, errors


def _call_with_fallbacks(
    client: NzMcpClient,
    tool: str,
    candidates: list[dict[str, Any]],
) -> ToolResult:
    last: ToolResult | None = None
    for args in candidates:
        last = client.call(tool, args)
        if last.ok:
            return last
    return (
        last
        if last is not None
        else ToolResult(ok=False, result=None, error_code="NO_ARGS", error_context=None)
    )


def _fallback_regex_references(ddl: str) -> list[Reference]:
    """Best-effort extraction when nz-mcp reference analyzer isn't available."""

    refs: list[Reference] = []

    def split_qual(name: str) -> tuple[str | None, str | None, str]:
        parts = [p for p in re.split(r"[.]", name) if p]
        if len(parts) == _QUAL_DB_SCHEMA_OBJ:
            return parts[0], parts[1], parts[2]
        if len(parts) == _QUAL_SCHEMA_OBJ:
            return None, parts[0], parts[1]
        return None, None, parts[-1] if parts else name

    for m in re.finditer(
        r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE)\s+([A-Z0-9_$.]+)",
        ddl,
        re.IGNORECASE,
    ):
        op = m.group(1).split()[0].upper()
        ref_db, ref_schema, ref_obj = split_qual(m.group(2))
        refs.append(
            Reference(
                kind="write",
                op=op,
                ref_database=ref_db,
                ref_schema=ref_schema,
                ref_object=ref_obj,
                line_from=None,
                line_to=None,
            )
        )

    for m in re.finditer(r"\b(CALL|EXEC(?:UTE)?)\s+([A-Z0-9_$.]+)", ddl, re.IGNORECASE):
        op = "CALL" if m.group(1).upper().startswith("CALL") else "EXEC"
        ref_db, ref_schema, ref_obj = split_qual(m.group(2))
        refs.append(
            Reference(
                kind="call",
                op=op,
                ref_database=ref_db,
                ref_schema=ref_schema,
                ref_object=ref_obj,
                line_from=None,
                line_to=None,
            )
        )

    for m in re.finditer(r"\b(FROM|JOIN)\s+([A-Z0-9_$.]+)", ddl, re.IGNORECASE):
        ref_db, ref_schema, ref_obj = split_qual(m.group(2))
        refs.append(
            Reference(
                kind="read",
                op="SELECT",
                ref_database=ref_db,
                ref_schema=ref_schema,
                ref_object=ref_obj,
                line_from=None,
                line_to=None,
            )
        )

    return refs


def _index_one(
    *,
    client: NzMcpClient,
    chroma: ChromaStore,
    metadata: MetadataStore,
    embedder: Embedder,
    proc: _ProcInfo,
) -> tuple[int, int, str | None]:
    key = ProcedureKey(
        database=proc.database,
        schema=proc.schema,
        name=proc.name,
        signature=proc.signature,
    )

    ddl_res = _call_with_fallbacks(
        client,
        _TOOL_GET_DDL,
        [
            {"database": proc.database, "schema": proc.schema, "procedure": proc.name},
            {"database": proc.database, "schema": proc.schema, "name": proc.name},
            {"database": proc.database, "procedure": f"{proc.schema}.{proc.name}"},
            {"database": proc.database, "target": f"{proc.schema}.{proc.name}"},
        ],
    )
    ddl = _extract_text(ddl_res, keys=("ddl", "body", "source"))
    if ddl is None:
        detail = f"{proc.database}.{proc.schema}.{proc.name}"
        return (
            0,
            0,
            f"failed to fetch DDL for {detail}: {ddl_res.error_code}",
        )

    body_hash = _sha256(ddl)
    previous_hash = metadata.get_body_sha256(key)
    previous_chunker = metadata.get_chunker_version(key)
    if (
        previous_hash is not None
        and previous_hash == body_hash
        and previous_chunker == CHUNKER_VERSION
    ):
        return 0, 0, None

    # Remove prior chunks to avoid stale chunk IDs when chunk counts shrink.
    chroma.delete_by_procedure(proc.database, proc.schema, proc.name)

    chunks = chunk(ddl)
    vectors = embedder.embed([c.text for c in chunks])
    ids = [
        f"{proc.database}.{proc.schema}.{proc.name}:{proc.signature}:{idx}"
        for idx in range(len(chunks))
    ]
    metadatas: list[dict[str, Any]] = []
    documents: list[str] = []
    for c in chunks:
        metadatas.append(
            {
                "database": proc.database,
                "schema": proc.schema,
                "procedure": proc.name,
                "signature": proc.signature,
                "line_from": c.line_from,
                "line_to": c.line_to,
                "section_hint": c.section_hint,
            }
        )
        documents.append(c.text)

    chroma.upsert(ids=ids, vectors=vectors, metadatas=metadatas, documents=documents)

    # nz-mcp doesn't expose a reference-analysis tool today; regex extraction
    # over the DDL covers the structural queries we need (writers, callers).
    # If a semantic analyzer lands in nz-mcp later, re-introduce the call here.
    references = _fallback_regex_references(ddl)

    metadata.upsert_procedure(
        key,
        last_altered=proc.last_altered,
        body_sha256=body_hash,
        chunker_version=CHUNKER_VERSION,
    )
    metadata.upsert_references(key, references)

    return 1, len(chunks), None


def bootstrap(
    databases: list[str],
    top_n: int | None = None,
    *,
    on_progress: ProgressCallback | None = None,
) -> IndexReport:
    """Index all (or top-N) procedures in the given PROD databases.

    ``on_progress`` is invoked with dict events (see ``ProgressEvent``) so callers
    can render a CLI progress bar or telemetry without the indexer caring how.
    """

    t0 = time.perf_counter()
    errors: list[str] = []
    procedures_indexed = 0
    procedures_skipped = 0
    chunks_written = 0
    total_discovered = 0

    cfg = load_config()
    metadata = MetadataStore(cfg.state_dir / "metadata.sqlite")
    metadata.ensure_schema()
    chroma = ChromaStore(cfg.state_dir)
    embedder = make_embedder(cfg.embedder_model)
    client = NzMcpClient(bin_path=cfg.nz_mcp_bin)

    try:
        client.start()
        for db in databases:
            schemas, err = _list_schema_names(client, db)
            if err is not None:
                errors.append(err)
                continue

            for schema_name in schemas:
                procs, proc_err = _list_procedures_in_schema(client, db, schema_name)
                if proc_err is not None:
                    errors.append(proc_err)
                    continue

                if top_n is not None and top_n > 0:
                    procs.sort(key=lambda p: p.size_bytes or 0, reverse=True)
                    procs = procs[:top_n]

                total_discovered += sum(_work_units(p) for p in procs)
                if on_progress is not None:
                    on_progress({"stage": "total_update", "total": total_discovered})

                newly_indexed, newly_skipped, newly_chunks, proc_errors = _index_procedures(
                    procs=procs,
                    client=client,
                    chroma=chroma,
                    metadata=metadata,
                    embedder=embedder,
                    on_progress=on_progress,
                )
                procedures_indexed += newly_indexed
                procedures_skipped += newly_skipped
                chunks_written += newly_chunks
                errors.extend(proc_errors)
    finally:
        client.stop()

    duration = time.perf_counter() - t0
    if procedures_indexed == 0 and procedures_skipped == 0 and not errors:
        errors.append(
            "no procedures were discovered in any database. Verify that nz_list_schemas + "
            "nz_list_procedures are available and that the profile has visibility over the "
            "requested databases."
        )
    return IndexReport(
        procedures_indexed=procedures_indexed,
        procedures_skipped=procedures_skipped,
        chunks_written=chunks_written,
        duration_seconds=duration,
        errors=errors,
    )


def refresh_one(
    database: str,
    schema: str,
    procedure: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> IndexReport:
    """Re-index a single procedure when its source changed in PROD."""

    t0 = time.perf_counter()
    errors: list[str] = []

    cfg = load_config()
    metadata = MetadataStore(cfg.state_dir / "metadata.sqlite")
    metadata.ensure_schema()
    chroma = ChromaStore(cfg.state_dir)
    embedder = make_embedder(cfg.embedder_model)
    client = NzMcpClient(bin_path=cfg.nz_mcp_bin)

    procedures_indexed = 0
    procedures_skipped = 0
    chunks_written = 0

    try:
        client.start()
        proc_info = _ProcInfo(
            database=database,
            schema=schema,
            name=procedure,
            signature="()",
            last_altered="",
            size_bytes=None,
        )
        if on_progress is not None:
            on_progress({"stage": "total_update", "total": 1})
            on_progress(
                {
                    "stage": "proc_start",
                    "database": database,
                    "schema": schema,
                    "name": procedure,
                }
            )
        indexed, chunks, err = _index_one(
            client=client,
            chroma=chroma,
            metadata=metadata,
            embedder=embedder,
            proc=proc_info,
        )
        if err is not None:
            errors.append(err)
        elif indexed == 0:
            procedures_skipped = 1
        else:
            procedures_indexed = 1
            chunks_written = chunks
        if on_progress is not None:
            on_progress(
                {
                    "stage": "proc_done",
                    "database": database,
                    "schema": schema,
                    "name": procedure,
                    "chunks": chunks,
                    "indexed": indexed == 1,
                    "skipped": indexed == 0 and err is None,
                    "error": err,
                    "work_units": 1,
                }
            )
    finally:
        client.stop()

    return IndexReport(
        procedures_indexed=procedures_indexed,
        procedures_skipped=procedures_skipped,
        chunks_written=chunks_written,
        duration_seconds=time.perf_counter() - t0,
        errors=errors,
    )


def refresh_cron(*, on_progress: ProgressCallback | None = None) -> IndexReport:
    """Scan ``_V_PROCEDURE.LASTALTERTIME`` and re-index changed procedures (best-effort).

    Requires that procedures have been bootstrapped before, so the local metadata
    store already contains the list of databases to refresh.
    """

    t0 = time.perf_counter()
    cfg = load_config()
    metadata = MetadataStore(cfg.state_dir / "metadata.sqlite")
    metadata.ensure_schema()

    databases = metadata.list_indexed_databases()
    if not databases:
        return IndexReport(
            procedures_indexed=0,
            procedures_skipped=0,
            chunks_written=0,
            duration_seconds=time.perf_counter() - t0,
            errors=["no indexed databases found; run kb-bootstrap first"],
        )

    report = bootstrap(databases, top_n=None, on_progress=on_progress)
    return IndexReport(
        procedures_indexed=report.procedures_indexed,
        procedures_skipped=report.procedures_skipped,
        chunks_written=report.chunks_written,
        duration_seconds=time.perf_counter() - t0,
        errors=report.errors,
    )


__all__ = [
    "IndexReport",
    "ProgressCallback",
    "ProgressEvent",
    "bootstrap",
    "refresh_cron",
    "refresh_one",
]
