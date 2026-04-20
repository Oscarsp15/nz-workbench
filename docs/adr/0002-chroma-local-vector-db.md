# ADR 0002 — Chroma as the local vector store

- **Date**: 2026-04-19
- **Status**: accepted
- **Decided by**: Tech Lead + human validation via PR

## Context

The knowledge base must index up to ~6,300 procedures (18 PROD databases × ~350 SPs each) and serve semantic plus structural queries. Requirements:

- Local-first. No data leaves the developer's machine.
- No Docker, no separate server process — single-file storage preferred.
- Portable to another machine by copying files.
- Supports filters on metadata (database, schema, procedure).
- Free and open source.
- Active maintenance.

Team size is small (3 developers max). Expected query volume: a few hundred per day during active REN work.

## Decision

**Chroma (embedded mode)**. Chroma stores vectors and metadata in a SQLite file under `.nz-workbench/chroma/chroma.sqlite3`. No external server, no Docker image required. Python client is the only dependency.

## Consequences

- **Positive**:
  - Zero operational overhead. `pip install chromadb` and go.
  - Single-file storage — portable by `cp` or `rsync`.
  - Supports metadata filters natively.
  - Collection abstraction matches our model (one collection per database or one global — TBD in `kb/chroma_store.py`).
- **Negative**:
  - Embedded SQLite does not support concurrent writes from multiple processes. Not a concern today (single user) but a future migration to a shared instance will require switching to Chroma server mode or another store.
  - Chroma schema evolves between versions; re-indexing may be needed on upgrades.
- **Neutral**:
  - Vector search performance on ~6,300 × ~15 chunks ≈ 100k vectors with 1024 dims is fast on a laptop (< 100 ms per query).

## Alternatives considered

- **Qdrant (Docker)**: more performant and scalable, but requires running a container. Overkill for day-1 single-user scenario. **Will revisit** when the team grows or we move to a shared server — migration path is straightforward since our wrapper (`kb/chroma_store.py`) keeps the integration narrow.
- **LanceDB**: file-based, promising, but less mature Python ecosystem and smaller community than Chroma.
- **pgvector on a local Postgres**: operational overhead of running Postgres outweighs any benefit at this scale.
- **FAISS**: powerful but index-only, no metadata filtering out of the box. Would require our own metadata layer.
