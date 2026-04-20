"""SQLite store for structural procedure metadata (reads / writes / calls).

Populated by the indexer using ``nz_analyze_procedure_references`` from nz-mcp.
Consumed by structural queries (e.g. "which SPs write to table X?").
"""

from __future__ import annotations

import sqlite3
import time
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
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        """Create tables and indexes if not present."""

        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS procedure (
                    database       TEXT NOT NULL,
                    schema         TEXT NOT NULL,
                    name           TEXT NOT NULL,
                    signature      TEXT NOT NULL,
                    last_altered   TEXT,
                    body_sha256    TEXT,
                    indexed_at     TEXT NOT NULL,
                    PRIMARY KEY (database, schema, name, signature)
                );

                CREATE TABLE IF NOT EXISTS sp_reference (
                    database       TEXT NOT NULL,
                    schema         TEXT NOT NULL,
                    name           TEXT NOT NULL,
                    signature      TEXT NOT NULL,
                    kind           TEXT NOT NULL,
                    op             TEXT NOT NULL,
                    ref_database   TEXT,
                    ref_schema     TEXT,
                    ref_object     TEXT NOT NULL,
                    line_from      INTEGER,
                    line_to        INTEGER,
                    FOREIGN KEY (database, schema, name, signature)
                        REFERENCES procedure (database, schema, name, signature) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_sp_reference_ref
                    ON sp_reference (ref_database, ref_schema, ref_object, kind);

                CREATE TABLE IF NOT EXISTS side_effect (
                    database       TEXT NOT NULL,
                    schema         TEXT NOT NULL,
                    name           TEXT NOT NULL,
                    pattern        TEXT NOT NULL,
                    default_action TEXT NOT NULL,
                    default_arg    TEXT,
                    noted_at       TEXT NOT NULL,
                    noted_by       TEXT
                );
                """
            )

    def upsert_procedure(self, key: ProcedureKey, last_altered: str, body_sha256: str) -> None:
        """Insert or replace a procedure row."""

        indexed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO procedure (
                    database, schema, name, signature,
                    last_altered, body_sha256, indexed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(database, schema, name, signature)
                DO UPDATE SET last_altered=excluded.last_altered,
                              body_sha256=excluded.body_sha256,
                              indexed_at=excluded.indexed_at;
                """,
                (
                    key.database,
                    key.schema,
                    key.name,
                    key.signature,
                    last_altered,
                    body_sha256,
                    indexed_at,
                ),
            )

    def upsert_references(self, key: ProcedureKey, references: list[Reference]) -> None:
        """Replace all references for a procedure (used after re-indexing)."""

        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM sp_reference
                WHERE database=? AND schema=? AND name=? AND signature=?;
                """,
                (key.database, key.schema, key.name, key.signature),
            )
            conn.executemany(
                """
                INSERT INTO sp_reference (
                    database, schema, name, signature,
                    kind, op, ref_database, ref_schema, ref_object, line_from, line_to
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    (
                        key.database,
                        key.schema,
                        key.name,
                        key.signature,
                        ref.kind,
                        ref.op,
                        ref.ref_database,
                        ref.ref_schema,
                        ref.ref_object,
                        ref.line_from,
                        ref.line_to,
                    )
                    for ref in references
                ],
            )

    def procedures_writing_to(self, ref_object: str) -> list[ProcedureKey]:
        """Structural query: which SPs write to ``ref_object``."""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT database, schema, name, signature
                FROM sp_reference
                WHERE kind='write' AND ref_object=?;
                """,
                (ref_object,),
            ).fetchall()
        return [
            ProcedureKey(
                database=r["database"], schema=r["schema"], name=r["name"], signature=r["signature"]
            )
            for r in rows
        ]

    def procedures_calling(self, ref_schema: str, ref_object: str) -> list[ProcedureKey]:
        """Structural query: which SPs CALL ``ref_schema.ref_object``."""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT database, schema, name, signature
                FROM sp_reference
                WHERE kind='call' AND ref_schema=? AND ref_object=?;
                """,
                (ref_schema, ref_object),
            ).fetchall()
        return [
            ProcedureKey(
                database=r["database"], schema=r["schema"], name=r["name"], signature=r["signature"]
            )
            for r in rows
        ]

    # ----- helpers used by the indexer -----
    def get_body_sha256(self, key: ProcedureKey) -> str | None:
        """Return stored body hash for a procedure, if indexed."""

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT body_sha256 FROM procedure
                WHERE database=? AND schema=? AND name=? AND signature=?;
                """,
                (key.database, key.schema, key.name, key.signature),
            ).fetchone()
        return None if row is None else str(row["body_sha256"])

    def get_last_altered(self, key: ProcedureKey) -> str | None:
        """Return stored last_altered for a procedure, if present."""

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT last_altered FROM procedure
                WHERE database=? AND schema=? AND name=? AND signature=?;
                """,
                (key.database, key.schema, key.name, key.signature),
            ).fetchone()
        if row is None:
            return None
        value = row["last_altered"]
        return None if value is None else str(value)

    def list_indexed_databases(self) -> list[str]:
        """Return distinct databases present in the procedure table."""

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT database FROM procedure ORDER BY database;"
            ).fetchall()
        return [str(r["database"]) for r in rows]


__all__ = ["MetadataStore", "ProcedureKey", "RefKind", "Reference"]
