"""SQLite store for structural procedure metadata (reads / writes / calls).

Populated by the indexer using ``nz_analyze_procedure_references`` from nz-mcp.
Consumed by ``search_structural`` queries (e.g. "which SPs write to table X?").
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RefKind = Literal["read", "write", "call"]


@dataclass(frozen=True, slots=True)
class ProcedureKey:
    """Uniquely identify a procedure in the metadata store."""

    database: str
    schema: str
    name: str
    signature: str


@dataclass(frozen=True, slots=True)
class Reference:
    """One DB object referenced by a procedure."""

    kind: RefKind
    op: str  # SELECT | INSERT | UPDATE | DELETE | CREATE | CALL | EXEC
    ref_database: str | None
    ref_schema: str | None
    ref_object: str
    line_from: int | None
    line_to: int | None


class MetadataStore:
    """Thin wrapper around a SQLite file under .nz-workbench/metadata.sqlite."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def ensure_schema(self) -> None:
        """Create tables and indexes if not present."""
        raise NotImplementedError

    def upsert_procedure(self, key: ProcedureKey, last_altered: str, body_sha256: str) -> None:
        """Insert or replace a procedure row."""
        raise NotImplementedError

    def upsert_references(self, key: ProcedureKey, references: list[Reference]) -> None:
        """Replace all references for a procedure (used after re-indexing)."""
        raise NotImplementedError

    def procedures_writing_to(self, ref_object: str) -> list[ProcedureKey]:
        """Structural query: which SPs write to ``ref_object``."""
        raise NotImplementedError

    def procedures_calling(self, ref_schema: str, ref_object: str) -> list[ProcedureKey]:
        """Structural query: which SPs CALL ``ref_schema.ref_object``."""
        raise NotImplementedError


__all__ = ["MetadataStore", "ProcedureKey", "Reference", "RefKind"]
