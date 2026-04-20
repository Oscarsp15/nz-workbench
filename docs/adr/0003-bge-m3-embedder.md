# ADR 0003 — BGE-M3 as the embedding model

- **Date**: 2026-04-19
- **Status**: accepted
- **Decided by**: Tech Lead + human validation via PR

## Context

Procedures in our organization mix Spanish (comments, variable names, business terms) with SQL English keywords and column names. Semantic search must work well across:

- Conceptual queries in Spanish: *"donde se calcula el saldo de cascada"*.
- Literal identifier queries: *"BASECOMERCIAL_EFECTIVO_MC"*, *"NROORDEN"*.
- Mixed: *"LEFT JOIN con BASECOMERCIAL para traer TIPOCLIENTE"*.

Embedding model must:

- Support multilingual content (Spanish + English) with strong quality.
- Run on local CPU (no API costs, no data leakage).
- Handle chunks up to 400 tokens comfortably.
- Support keyword-like matching for exact identifier names.

## Decision

**BAAI/bge-m3** via `sentence-transformers`.

- Dimensions: 1024 (dense).
- Context window: 8192 tokens.
- License: MIT.
- Native support for hybrid retrieval (dense + sparse + multi-vector in one model), which matches our need for both semantic and literal matching.

## Consequences

- **Positive**:
  - Single model covers conceptual and literal retrieval — no need to run a separate keyword indexer.
  - Multilingual performance is state-of-the-art among open-source models on Spanish-heavy datasets.
  - Runs on CPU acceptably (~50 chunks/sec on a modern laptop). Full bootstrap of ~100k chunks in ~2 hours.
- **Negative**:
  - Model weights are ~2.3 GB. First download is slow on limited bandwidth.
  - Inference is slower than smaller single-purpose embedders like `all-MiniLM-L6-v2`. Accepted as cost of multilingual + hybrid.
- **Neutral**:
  - We use only the dense component in phase 1 for simplicity. Sparse and multi-vector are available if we need to upgrade retrieval later.

## Alternatives considered

- **`intfloat/multilingual-e5-large`**: strong multilingual, slightly smaller. No hybrid. Rejected because hybrid quality on identifier-heavy content is noticeably better with BGE-M3.
- **`sentence-transformers/paraphrase-multilingual-mpnet-base-v2`**: lighter (~1 GB), older. Quality gap vs BGE-M3 is significant on MIRACL benchmarks.
- **OpenAI `text-embedding-3-large` / Cohere `embed-multilingual-v3`**: top quality but external API. Rejected per locality requirement (business logic cannot leave the org).
- **Jina v3**: licensed CC-BY-NC. Rejected per license incompatibility with any future commercial extension.
