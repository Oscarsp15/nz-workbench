# REN lifecycle

The canonical flow from REN ingestion to a merged, documented change. Each step produces a concrete artifact under `ren/REN_<N>/`.

## Phases and gates

```
┌──────────────┐       ┌──────────────┐      ┌────────────────┐
│  Phase 1     │       │  Phase 2     │      │  Phase 3       │
│  Ingest      │──────▶│  Analysis    │──────▶│  GATE 1:       │
│              │       │  (AI only)   │      │  Clarifications│
└──────────────┘       └──────────────┘      └────────┬───────┘
                                                      │ human resolves
                                                      ▼
┌──────────────┐       ┌──────────────┐      ┌────────────────┐
│  Phase 6     │       │  Phase 5     │      │  Phase 4       │
│  Baseline    │◀──────│  Clone       │◀──────│  Manifest      │
│  test        │       │              │      │                │
└──────┬───────┘       └──────────────┘      └────────────────┘
       │ baseline OK
       ▼
┌──────────────┐       ┌──────────────┐      ┌────────────────┐
│  Phase 7     │       │  Phase 8     │      │  GATE 2:       │
│  Edits       │──────▶│  Comparison  │──────▶│  Final review  │
│              │       │              │      │                │
└──────────────┘       └──────────────┘      └────────┬───────┘
                                                      │ human approves
                                                      ▼
                                             ┌────────────────┐
                                             │  Phase 9       │
                                             │  Document      │
                                             └────────────────┘
```

## Phase 1 — Ingest

Human pastes the REN document into the Claude CLI session or saves it as `ren/REN_<N>/source.md`.

Artifact: `ren/REN_<N>/source.md`.

## Phase 2 — Analysis (AI autonomous)

The AI runs in sequence:

1. Extracts entities from the REN text — tables, columns, operations, numeric thresholds, code fragments.
2. Queries the KB structurally for SPs that write or call the mentioned objects.
3. Queries the KB semantically for each described change.
4. Produces `analysis.yaml` listing candidate SPs and their confidence, plus an enumerated list of change points with line ranges.
5. Emits `clarifications.md` with one question per ambiguity (see `AGENTS.md` § 2.2).

Artifacts: `analysis.yaml`, `clarifications.md`.

## Gate 1 — Clarifications (human)

The human reads `clarifications.md`, takes the questions to the business user or the team, and writes the answers back to the same file. No further phase runs until every question has an answer.

Typical channels: chat, meeting, email. Format is free text; the AI parses it.

## Phase 4 — Manifest

With a clean analysis, the AI produces `manifest.yaml`:

```yaml
ren: 35145
suffix: "_35145"
procedures:
  - source: PROD_MAESTROBI.DBO.PI_ASIG_DESEMB_CANAL_2026
    target:
      database: DESA_MAESTROBI
      schema: DBO
      name: PI_ASIG_DESEMB_CANAL_2026_35145
tables_to_clone:
  - PROD_MAESTROBI.DBO.EFE_MC_CREDITOSNOASIGNADOS
procedures_to_call_with_suffix: []   # other SPs whose calls inside this one should receive the REN suffix
side_effects_overrides:
  - pattern: "CALL PROD_MAESTROBI.DBO.MAIL_*"
    action: redirect_to
    arg: oscar.sirlopu@e2e.pe
```

The human validates and amends by hand if needed. This file is the contract for the rest of the lifecycle.

## Phase 5 — Clone

Using `manifest.yaml`, the AI invokes `nz_clone_procedure` from `nz-mcp` per source SP, with the transformations derived from the rules in `docs/architecture/prod-desa-rules.md`. The clones are created in the target `DESA_*` database but with no change points applied yet.

Artifacts: dry-run DDLs saved under `ren/REN_<N>/diffs/baseline-cloned/`.

## Phase 6 — Baseline test

Critical integrity check. The AI:

1. Runs the original PROD SP with a reference parameter set (typically the previous month's closing date).
2. Runs the unmodified clone with the same parameters.
3. Compares every final output table (all tables the SP writes to) between PROD and DESA.

If results are identical, the environment is parity-correct — the REN changes will produce diffs exclusively due to the changes, not environmental drift.

If results differ, phase 6 fails and the lifecycle stops. The AI produces a report of the differences and possible causes (side effects, permissions, timestamp skew) in `baseline_test.md`.

Artifact: `baseline_test.md`.

## Phase 7 — Edits

For each change point in `analysis.yaml`, the AI:

1. Reads the target section of the cloned SP.
2. Produces the edited SQL.
3. Shows the diff.
4. Applies it via `CREATE OR REPLACE PROCEDURE` on the clone.

Change points are applied in the order specified by `analysis.yaml`. If one fails, the sequence stops and a human reviews.

Artifacts: one file per change point under `ren/REN_<N>/diffs/cp-<id>.diff`.

## Phase 8 — Comparison

The AI re-runs the now-modified clone with the same reference parameters as phase 6. Compares every final output table between PROD and modified DESA. Produces `test_report.md` with row counts, per-dimension aggregates (e.g. per canal, per status), and a sample of rows that differ.

Some diffs are expected — they are the intent of the REN. The report highlights each expected category.

Unexpected diffs are explicitly flagged.

Artifact: `test_report.md`.

## Gate 2 — Final review (human)

Oscar reads `test_report.md` and the per-change-point diffs. Decides:

- Approve → phase 9.
- Iterate → go back to phase 7 with adjustments.
- Abort → document the reason in `summary.md` and close the REN without applying.

## Phase 9 — Documentation

The AI updates three places:

1. `docs/procedures/<SP>.md` for each modified SP — appends a "Change log" entry referencing the REN and summarizing the changes in plain language.
2. `docs/learning-log.md` — appends an entry with what was learned in this REN (new business rules, patterns, side effects catalogued).
3. `ren/REN_<N>/summary.md` — final TL;DR, status (applied / aborted), links to all other artifacts.

Commits are phase-scoped (`analysis(...)`, `clone(...)`, `edit(...)`, `test(...)`, `docs(...)`) so the REN history is readable in `git log`.

## Artifacts per REN (complete listing)

```
ren/REN_35145/
├── source.md                 # Phase 1
├── analysis.yaml             # Phase 2
├── clarifications.md         # Phase 2 + Gate 1
├── manifest.yaml             # Phase 4
├── diffs/                    # Phase 5, 7
│   ├── baseline-cloned/
│   │   └── <SP>.sql
│   ├── cp-1.diff
│   ├── cp-2.diff
│   └── …
├── baseline_test.md          # Phase 6
├── test_report.md            # Phase 8
├── decisions.md              # accumulated through phases 4, 7
├── conversation.md           # transcript of CLI session (optional)
└── summary.md                # Phase 9
```
