"""Chroma-backed vector store for procedure chunks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One result from a semantic / hybrid search."""

    database: str
    schema: str
    procedure: str
    line_from: int
    line_to: int
    score: float
    text_preview: str
    metadata: dict[str, Any]


class ChromaStore:
    """Wraps the Chroma client for this project's access patterns."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str],
    ) -> None:
        """Store or replace a batch of chunks."""
        raise NotImplementedError

    def search_semantic(
        self,
        query_vector: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        """Dense retrieval — top-k chunks by cosine similarity."""
        raise NotImplementedError

    def delete_by_procedure(self, database: str, schema: str, procedure: str) -> None:
        """Drop all chunks for a given procedure (used by kb-refresh)."""
        raise NotImplementedError


__all__ = ["ChromaStore", "SearchHit"]
