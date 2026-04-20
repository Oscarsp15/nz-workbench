"""Chroma-backed vector store for procedure chunks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

_COLLECTION_NAME: Final[str] = "procedure_chunks"

_CHROMADB: Any | None = None
_imported_chromadb: Any
try:
    import chromadb as _imported_chromadb
except Exception:  # pragma: no cover
    _imported_chromadb = None
else:
    _CHROMADB = _imported_chromadb


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
        self._chroma_dir = self._root / "chroma"
        self._chroma_dir.mkdir(parents=True, exist_ok=True)

        if _CHROMADB is None:  # pragma: no cover
            raise RuntimeError("chromadb is required to use the knowledge base vector store")

        chroma = cast(Any, _CHROMADB)
        self._client = chroma.PersistentClient(path=str(self._chroma_dir))
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str],
    ) -> None:
        """Store or replace a batch of chunks."""

        if not ids:
            return
        collection = cast(Any, self._collection)
        collection.upsert(
            ids=ids,
            embeddings=vectors,
            metadatas=metadatas,
            documents=documents,
        )

    def search_semantic(
        self,
        query_vector: list[float],
        k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        """Dense retrieval — top-k chunks by cosine similarity."""

        where = self._normalize_where(filters)
        collection = cast(Any, self._collection)
        res = collection.query(
            query_embeddings=[query_vector],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[SearchHit] = []
        ids_batch = cast(list[list[str]], res.get("ids") or [[]])
        docs_batch = cast(list[list[str]], res.get("documents") or [[]])
        metas_batch = cast(list[list[dict[str, Any]]], res.get("metadatas") or [[]])
        dists_batch = cast(list[list[float]], res.get("distances") or [[]])

        for _id, doc, meta, dist in zip(
            ids_batch[0],
            docs_batch[0],
            metas_batch[0],
            dists_batch[0],
            strict=False,
        ):
            metadata = {} if meta is None else dict(meta)
            database = str(metadata.get("database", ""))
            schema = str(metadata.get("schema", ""))
            procedure = str(metadata.get("procedure", ""))
            line_from = int(metadata.get("line_from", 0) or 0)
            line_to = int(metadata.get("line_to", 0) or 0)
            distance = float(dist) if dist is not None else 1.0
            score = 1.0 - distance
            preview = (doc or "")[:200].replace("\n", " ")
            hits.append(
                SearchHit(
                    database=database,
                    schema=schema,
                    procedure=procedure,
                    line_from=line_from,
                    line_to=line_to,
                    score=score,
                    text_preview=preview,
                    metadata=metadata,
                )
            )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def delete_by_procedure(self, database: str, schema: str, procedure: str) -> None:
        """Drop all chunks for a given procedure (used by kb-refresh)."""

        where = self._normalize_where(
            {"database": database, "schema": schema, "procedure": procedure}
        )
        collection = cast(Any, self._collection)
        collection.delete(where=where)

    @staticmethod
    def _normalize_where(filters: dict[str, Any] | None) -> dict[str, Any] | None:
        if not filters:
            return None
        if len(filters) == 1:
            return filters
        return {"$and": [{k: v} for k, v in filters.items()]}


__all__ = ["ChromaStore", "SearchHit"]
