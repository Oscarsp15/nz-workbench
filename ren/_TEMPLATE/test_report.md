# REN <N> — comparison report (post-edits)

<!--
  Phase 8 of the REN lifecycle.
  Runs the MODIFIED clone and compares output against PROD.
  Expected diffs are flagged per change point. Unexpected diffs require human review.
-->

## Parameters

- `P_FECCORTE`: `<value>`

## Environments

- **PROD**: `<PROD_DB.SCHEMA.SP>`
- **DESA (modified clone)**: `<DESA_DB.SCHEMA.SP_<N>>` — change points applied

## Executed at

<ISO timestamp>

## Summary

| Output table | PROD rows | DESA rows | Delta | Delta % |
|---|---|---|---|---|

## Per-dimension breakdown

<!-- Aggregate by relevant dimension (e.g. CANAL, TIPOCLIENTE, CODGESTION).
     One table per dimension. -->

### By CANAL

| CANAL | PROD | DESA | Delta |
|---|---|---|---|

## Expected diffs (mapped to change points)

<!--
  For each change point, explicitly state the expected impact on output.
  Check off each expected effect that is observed.
-->

- [ ] Change point 1 — <expected: "iGlobal_Campo drops because DistanciaXY > 50 reroutes to Canal Propio">
- [ ] Change point 2 — <expected>
- [ ] Change point 3 — <expected>

## Unexpected diffs (require review)

<!-- Rows or aggregates that differ but are not explained by any change point.
     These are potential bugs or side effects. List them here for the final review gate. -->

## Sample of rows that differ

<!-- Up to 20 rows where the same natural key has a different value in a meaningful column.
     Never full row dumps — sanitize PII. -->

## Overall verdict

- [ ] All diffs are expected. REN ready to close.
- [ ] Unexpected diffs present — iterate (back to phase 7).
- [ ] Abort — REN cannot be closed safely.
