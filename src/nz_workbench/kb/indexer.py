"""Bootstrap and incremental indexing of production procedures into the KB."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndexReport:
    """Result of an indexing pass."""

    procedures_indexed: int
    procedures_skipped: int
    chunks_written: int
    duration_seconds: float
    errors: list[str]


def bootstrap(databases: list[str], top_n: int | None = None) -> IndexReport:
    """Index all (or top-N) procedures in the given PROD databases.

    Placeholder — full implementation will:
    1. List procedures via nz-mcp (``nz_list_procedures``).
    2. For each, fetch DDL (``nz_get_procedure_ddl``).
    3. Chunk, embed (BGE-M3 local), store in Chroma.
    4. Run ``nz_analyze_procedure_references`` (nz-mcp tool) to fill SQLite.
    5. Report.
    """
    raise NotImplementedError


def refresh_one(database: str, schema: str, procedure: str) -> IndexReport:
    """Re-index a single procedure when its source changed in PROD."""
    raise NotImplementedError


def refresh_cron() -> IndexReport:
    """Scan ``_V_PROCEDURE.LASTALTERTIME`` and re-index everything newer than stored."""
    raise NotImplementedError


__all__ = ["IndexReport", "bootstrap", "refresh_one", "refresh_cron"]
