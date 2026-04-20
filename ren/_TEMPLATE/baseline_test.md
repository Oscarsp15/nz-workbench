# REN <N> — baseline test

<!--
  Phase 6 of the REN lifecycle.
  Runs PROD original and DESA clone WITH NO CHANGES and compares their output.
  If they differ, phase 6 fails and the lifecycle STOPS. No changes are applied.
-->

## Parameters

- `P_FECCORTE`: `<value from manifest.test_parameters>`

## Environments

- **PROD**: `<PROD_DB.SCHEMA.SP>`
- **DESA (clone)**: `<DESA_DB.SCHEMA.SP_<N>>` (cloned with `migrator` rules, no change points applied)

## Executed at

<ISO timestamp>

## Output tables compared

<!-- List every table the SP writes to. All must match for baseline to pass. -->

| Table | PROD rows | DESA rows | Match? |
|---|---|---|---|

## Per-dimension aggregates

<!-- For key dimensions (e.g. CANAL, PERIODO), compare aggregates. Same as PROD must equal DESA. -->

## Result

- [ ] Baseline PASSED — environments are in parity. Ready for phase 7 (edits).
- [ ] Baseline FAILED — divergence detected. Lifecycle stops.

## Failure analysis (if any)

<!-- If baseline failed, list candidate causes and evidence:
     - Timestamp skew between PROD and DESA
     - Permissions differ
     - Side effect not catalogued
     - Data drift (rare — ideally monitored upstream)
-->
