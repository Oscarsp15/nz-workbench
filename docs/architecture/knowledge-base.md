# Knowledge base

The knowledge base (KB) is what makes the AI genuinely useful across RENs. It combines semantic and structural search over every production procedure, plus accumulated human notes and AI explanations.

## Storage layout

```
.nz-workbench/                 (local, gitignored, portable)
├── chroma/                    Chroma vector store (SQLite file)
│   └── chroma.sqlite3
├── metadata.sqlite            Structural index (see schema below)
├── cache/                     Transient caches (embedder, LLM outputs)
│   ├── embeddings/
│   └── explanations/
└── version.json               KB schema version for migrations
```

```
docs/                          (committed to git)
├── procedures/<SP>.md         One file per SP — see `AGENTS.md` § 7
├── technical-decisions.md
├── side-effects-catalog.md
└── learning-log.md
```

## Metadata SQLite schema

```sql
-- Each procedure indexed from PROD_*.
CREATE TABLE procedure (
    database       TEXT NOT NULL,
    schema         TEXT NOT NULL,
    name           TEXT NOT NULL,
    signature      TEXT NOT NULL,
    last_altered   TEXT,            -- ISO timestamp from _V_PROCEDURE.LASTALTERTIME
    body_sha256    TEXT,
    indexed_at     TEXT NOT NULL,
    PRIMARY KEY (database, schema, name, signature)
);

-- Structural extraction: what does each SP read / write / call?
-- Populated by nz_analyze_procedure_references (tool added to nz-mcp).
CREATE TABLE sp_reference (
    database       TEXT NOT NULL,
    schema         TEXT NOT NULL,
    name           TEXT NOT NULL,
    signature      TEXT NOT NULL,
    kind           TEXT NOT NULL,    -- read | write | call
    op             TEXT NOT NULL,    -- SELECT | INSERT | UPDATE | DELETE | CREATE | CALL | EXEC
    ref_database   TEXT,
    ref_schema     TEXT,
    ref_object     TEXT NOT NULL,
    line_from      INTEGER,
    line_to        INTEGER,
    FOREIGN KEY (database, schema, name, signature)
        REFERENCES procedure (database, schema, name, signature) ON DELETE CASCADE
);

CREATE INDEX idx_sp_reference_ref ON sp_reference (ref_database, ref_schema, ref_object, kind);

-- Side effects observed per SP, with the action to take when cloning.
CREATE TABLE side_effect (
    database       TEXT NOT NULL,
    schema         TEXT NOT NULL,
    name           TEXT NOT NULL,
    pattern        TEXT NOT NULL,    -- e.g. "CALL PROD_X.DBO.MAIL_*"
    default_action TEXT NOT NULL,    -- comment_out | redirect_to | keep
    default_arg    TEXT,             -- e.g. email address for redirect_to
    noted_at       TEXT NOT NULL,
    noted_by       TEXT              -- "IA" | "Oscar"
);
```

## Chunking strategy

Each procedure body is split into chunks with these rules:

- Target size: 400 tokens per chunk (counted with the BGE-M3 tokenizer).
- Overlap: 50 tokens.
- Hard boundaries: split on `DECLARE`, `BEGIN`, `EXCEPTION`, `END LOOP`, `END IF`, and top-level `;`.
- Never split inside a string literal, comment block, or inside parentheses of a single statement.

Each chunk is stored in Chroma with metadata:

```json
{
  "database": "PROD_MAESTROBI",
  "schema": "DBO",
  "procedure": "PI_ASIG_DESEMB_CANAL_2026",
  "signature": "(DATE)",
  "line_from": 120,
  "line_to": 175,
  "section_hint": "body|declare|header|exception",
  "has_tables": ["EXT_MC_GESTIONCANALES", "TT_GESTION_CANALES"]
}
```

## Embedding model

**BAAI/bge-m3** via `sentence-transformers`. Chosen for:

- Strong multilingual performance (Spanish / English mix present in procedures).
- Native hybrid retrieval: dense embeddings for semantic meaning, sparse signals for exact keyword matches.
- 1024-dimensional dense vectors, context window 8192 tokens.
- MIT license, runs on CPU.

See [ADR 0003](../adr/0003-bge-m3-embedder.md).

## Retrieval modes

### `kb.search_semantic(query, k=10, filters={...})`

Pure dense retrieval using the query's BGE-M3 embedding. Returns top-k chunks ordered by cosine similarity. Filters: database, schema, procedure name prefix.

Use when the question is conceptual: *"donde se calcula el saldo de cascada para canal directo"*.

### `kb.search_structural(table=None, column=None, kind=None)`

Pure SQL query against `sp_reference`. Returns a list of `(procedure, line_range)` tuples.

Use when the question is literal: *"which SPs write to `EFE_MC_CREDITOSNOASIGNADOS`"*.

### `kb.search_hybrid(query, k=10, filters={...})`

Combines both. Runs the semantic search, then boosts results that also match the structural filters (e.g. contain a specific table).

Use by default — it handles both conceptual and literal queries with minimal effort on the caller's part.

## Refresh strategy

Initial bootstrap (`nz-workbench kb-bootstrap`) indexes every PROD procedure once. Estimated cost: ~2 hours of CPU time on a laptop for ~6,300 procedures, ~1–2 GB of disk. Zero Claude tokens.

Incremental updates:

- **Manual**: `nz-workbench kb-refresh <db>.<schema>.<sp>` re-indexes a single procedure.
- **Cron (opt-in)**: `nz-workbench kb-refresh-cron` compares `_V_PROCEDURE.LASTALTERTIME` against the indexed `last_altered` column and re-indexes any procedure whose timestamp changed.

Disabled by default. Expected drift in our environment: 4–5 procedures per week, rarely more.

## Explanations (Claude-powered)

Separate from raw indexing. When a human runs `nz-workbench learn <sp>`:

1. Fetches the full DDL via `nz-mcp`.
2. Sends it to Claude with a pedagogical prompt to produce a block-by-block mapping.
3. Stores the result in `docs/procedures/<SP>.md` under "IA mapping (auto)".
4. Re-indexes that file contents so future semantic searches can retrieve the explanation alongside the raw body.

This step *does* consume Claude tokens. It is always triggered explicitly by the human or by the REN analyzer when a touched SP has no prior explanation.
