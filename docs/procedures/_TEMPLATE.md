# <PROCEDURE_NAME>

<!--
  Canonical structure for a procedure knowledge file.
  Four sections with strict ownership:
  - "Metadata (auto)": AI maintains
  - "IA mapping (auto)": AI maintains
  - "Notas humanas (manual)": only Oscar edits — AI never writes here
  - "Change log (auto)": AI appends one entry per REN that touches the SP
-->

## Metadata (auto)

<!-- _Generated YYYY-MM-DD — auto-update OK_ -->

- **Database**: `<PROD_*>`
- **Schema**: `<schema>`
- **Signature**: `<args>`
- **Last altered in source**: `<ISO date>`
- **Last indexed**: `<ISO date>`
- **Body SHA-256 (short)**: `<12 chars>`

## IA mapping (auto)

<!-- _Generated YYYY-MM-DD — auto-update OK_ -->

### Purpose (one line)

<What this procedure accomplishes in business terms.>

### Architecture (blocks)

- **Lines 1–N**: header + declarations (`N` parameters, `M` variables).
- **Lines …**: <block description>.
- **Lines …**: <block description>.

### External reads (preserved in DESA clones)

- `PROD_<db>.<schema>.<table>` — <what we use it for>.

### External writes (redirected to DESA in clones)

- `PROD_<db>.<schema>.<table>` — inserts / updates / deletes.

### Calls to other procedures

- `PROD_<db>.<schema>.<proc>` — <role>.

### Known side effects

- <CALL to mail / notification / audit — see `docs/side-effects-catalog.md` for the action>.

## Notas humanas (manual)

<!-- Solo edición manual. La IA no toca esta sección.
     Agregá notas, correcciones, contexto que la IA no puede inferir. -->

<!-- EXAMPLE:
- 2026-04-20 (Oscar): el CASE de línea 340 prioriza así porque el canal 1 (Aden)
  es contractualmente preferente sobre iGlobal cuando ambos tienen gestión válida.
-->

## Change log (auto)

<!-- IA appends a new entry every time a REN modifies this procedure. -->

<!-- EXAMPLE:
### 2026-04-19 — REN 35145

Agregó BMK05 al CASE de prioridad. Incorporó LEFT JOIN a BASECOMERCIAL_EFECTIVO_MC
para traer TIPOCLIENTE. Ajustó rango de fechas en TT_GESTION_CANALES para meses
de 31 días (día 25 vs 26). Aplicadas reglas de asignación forzada para
CODCANALORIGINACION 12/13.

- Clone: `DESA_MAESTROBI.DBO.PI_ASIG_DESEMB_CANAL_2026_35145`
- REN folder: `ren/REN_35145/`
- Comparison diff: +244 Canal Propio, -436 iGlobal, -326 totals (expected).
-->
