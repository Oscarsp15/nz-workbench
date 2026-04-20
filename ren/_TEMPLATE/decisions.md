# REN <N> — decisions log

<!--
  Non-trivial choices made during this REN, with reasoning.
  Contrast with docs/technical-decisions.md (cross-REN patterns).
  This file is REN-specific. When a decision is reusable, copy it to the global file.
-->

## Decisions

<!-- EXAMPLE

### D1 — UPDATE syntax for the forced-assignment block

- **Options considered**:
  - A) UPDATE with subquery: `UPDATE t SET col = (SELECT … FROM otra WHERE …)`
  - B) MERGE INTO
- **Chosen**: A
- **Reason**: user confirmed preference for subquery; MERGE generates different locking behavior in NPS 11.x that we have not validated.

### D2 — Where to place the LEFT JOIN to BASECOMERCIAL_EFECTIVO_MC

- **Options**:
  - A) Right after TT_GESTION_CANALES creation (line ~280)
  - B) Inside the final query (line ~520)
- **Chosen**: B
- **Reason**: TT_GESTION_CANALES does not use TIPOCLIENTE; introducing the join earlier adds an unused column to the temp table.

-->
