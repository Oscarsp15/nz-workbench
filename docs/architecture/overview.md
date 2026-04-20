# Architecture — overview

## High-level diagram

```
                     ┌─────────────────────────────┐
                     │  Human: Oscar               │
                     │  Claude Code CLI / Desktop  │
                     └──────────────┬──────────────┘
                                    │ MCP (stdio)
                                    ▼
                     ┌─────────────────────────────┐
                     │  nz-workbench MCP server    │
                     │  (this project)             │
                     └──┬─────────────┬─────────┬──┘
         ┌──────────────┘             │         └────────────┐
         ▼                            ▼                      ▼
┌─────────────────┐         ┌─────────────────┐    ┌─────────────────┐
│  nz-mcp client  │         │  Knowledge base │    │  Docs writer    │
│                 │         │  Chroma + SQLite│    │  docs/ + ren/   │
└────────┬────────┘         └────────┬────────┘    └─────────────────┘
         │ MCP (subprocess)          │
         ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│     nz-mcp      │         │   BGE-M3        │
│  (public tool)  │         │   (local)       │
└────────┬────────┘         └─────────────────┘
         │ nzpy
         ▼
┌─────────────────┐
│    Netezza      │
│  PROD_* / DESA_*│
└─────────────────┘
```

## Four internal modules

### `kb/` — knowledge base

The memory of the project. Indexes procedure bodies, accumulated explanations, and human notes.

Responsibilities:
- Chunk NZPLSQL procedure bodies into semantically coherent segments (~400 tokens each).
- Generate multilingual embeddings via BGE-M3 running on local CPU.
- Store vectors in Chroma and metadata (writes / reads / calls per procedure) in SQLite.
- Serve semantic and structural queries: *"where is the cascade priority CASE?"*, *"which SPs write to `EFE_MC_CREDITOSNOASIGNADOS`?"*.

No Claude tokens are consumed. All inference is local.

### `analyzer/` — REN parsing and clarifications

Turns a REN document into a structured plan of change points and a list of clarifications the human must resolve.

Responsibilities:
- Parse the REN markdown, extracting tables, columns, operations, and requested changes.
- Run semantic + structural searches against `kb/` to localize where each change likely applies.
- For each ambiguity (see `AGENTS.md` § 2.2) emit a question to the human.
- Produce `ren/REN_<N>/analysis.yaml`.

### `migrator/` — PROD → DESA rules

Applies the mechanical rewrite from PROD to DESA with the REN suffix.

Responsibilities:
- Load the REN manifest (`manifest.yaml`).
- For each source procedure, request its DDL via `nz-mcp` and apply the rules in `docs/architecture/prod-desa-rules.md`.
- Consult `docs/side-effects-catalog.md` to comment or redirect side effects.
- Invoke `nz_clone_procedure` from `nz-mcp` with the computed transformations.
- Produce the per-procedure DDL diffs under `ren/REN_<N>/diffs/`.

### `tester/` — baseline and comparison

Verifies that clones behave as expected against PROD.

Responsibilities:
- **Baseline**: run the original PROD procedure and the unmodified clone. Compare their output tables. Block if they differ.
- **Comparison**: after change points are applied, re-run the modified clone. Compare its output against PROD. Report row counts, key metrics, and a sample of differing rows.
- Produce `ren/REN_<N>/baseline_test.md` and `test_report.md`.

## Module dependencies

```
cli / mcp_server
     │
     ├──▶ analyzer ──▶ kb
     ├──▶ migrator ──▶ nz_mcp_client ──▶ nz-mcp
     ├──▶ tester   ──▶ nz_mcp_client
     └──▶ docs_writer
```

No circular imports. Every module depends only on what is strictly below it.

## Supporting docs

- [`knowledge-base.md`](knowledge-base.md) — data model, chunking strategy, embedder, refresh rules.
- [`ren-lifecycle.md`](ren-lifecycle.md) — step-by-step flow from REN ingest to documented close.
- [`prod-desa-rules.md`](prod-desa-rules.md) — the exact rewrite rules and examples.
