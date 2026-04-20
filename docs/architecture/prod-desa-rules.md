# PROD → DESA rewrite rules

These rules are applied by `migrator/` when cloning a procedure from a `PROD_*` database to its `DESA_*` counterpart. They are driven by the REN manifest (`manifest.yaml`) — the manifest determines what gets the REN suffix; the rules below determine the prefix rewrite.

## Principles

- **Never write to PROD from a clone.** Every write operation redirects from `PROD_*` to `DESA_*`.
- **Reads stay intact.** Selects against `PROD_*` continue reading from production. This is intentional: the clone uses real data for realistic testing.
- **The manifest decides suffix.** Only targets listed in `manifest.yaml` receive the `_<REN>` suffix. Other references keep their original names.

## Rule table

| Operation | Prefix `PROD_*` → `DESA_*` | `_<REN>` suffix on target |
|---|---|---|
| `INSERT INTO <tbl>` where `<tbl>` is in manifest | yes | yes |
| `INSERT INTO <tbl>` where `<tbl>` is NOT in manifest | yes | no |
| `UPDATE <tbl>` where `<tbl>` is in manifest | yes | yes |
| `UPDATE <tbl>` where `<tbl>` is NOT in manifest | yes | no |
| `DELETE FROM <tbl>` where `<tbl>` is in manifest | yes | yes |
| `DELETE FROM <tbl>` where `<tbl>` is NOT in manifest | yes | no |
| `CREATE TEMPORARY TABLE <tbl>` | not applicable (temp tables are session-scoped) | no |
| `CREATE TABLE <tbl>` (permanent) where in manifest | yes | yes |
| `CREATE TABLE <tbl>` (permanent) where NOT in manifest | yes | no |
| `CALL <sp>` / `EXEC <sp>` where `<sp>` is in manifest | yes | yes |
| `CALL <sp>` / `EXEC <sp>` where `<sp>` is NOT in manifest | yes | no |
| `SELECT … FROM <tbl>` and any read (`JOIN`, `INNER JOIN`, `LEFT JOIN`, subqueries, `WITH` CTE source) | **no** (preserved as-is) | no |

## Examples

Given a procedure cloned under REN 35145 whose manifest lists `EFE_MC_CREDITOSNOASIGNADOS` as a table to clone and no other targets:

### Example 1: simple INSERT on a manifest table

```sql
-- PROD (original)
INSERT INTO PROD_MAESTROBI.DBO.EFE_MC_CREDITOSNOASIGNADOS (...)
SELECT ... FROM PROD_MAESTROBI.DBO.BASE_CREDITOS;

-- DESA (clone)
INSERT INTO DESA_MAESTROBI.DBO.EFE_MC_CREDITOSNOASIGNADOS_35145 (...)   -- prefix + suffix
SELECT ... FROM PROD_MAESTROBI.DBO.BASE_CREDITOS;                       -- read stays PROD
```

### Example 2: UPDATE on a non-manifest table

```sql
-- PROD
UPDATE PROD_MAESTROBI.DBO.OTRA_TABLA SET ... FROM PROD_MAESTROBI.DBO.X ...;

-- DESA (clone, OTRA_TABLA not in manifest)
UPDATE DESA_MAESTROBI.DBO.OTRA_TABLA SET ... FROM PROD_MAESTROBI.DBO.X ...;  -- prefix only, no suffix
```

### Example 3: nested CALL where the callee is in the manifest

```sql
-- PROD
CALL PROD_MAESTROBI.DBO.OTRO_SP(P_FECCORTE);

-- DESA (OTRO_SP is in manifest, so suffix applies)
CALL DESA_MAESTROBI.DBO.OTRO_SP_35145(P_FECCORTE);
```

### Example 4: nested CALL where the callee is NOT in the manifest

```sql
-- PROD
CALL PROD_MAESTROBI.DBO.HELPER_UTIL(X);

-- DESA (HELPER_UTIL not in manifest)
CALL DESA_MAESTROBI.DBO.HELPER_UTIL(X);   -- prefix rewrite only
```

### Example 5: temporary table (no rewrite at all)

```sql
-- PROD
CREATE TEMPORARY TABLE TT_GESTION_CANALES AS
SELECT ... FROM PROD_MAESTROBI.DBO.EXT_MC_GESTIONCANALES ...;

-- DESA (temp table untouched; read from PROD preserved)
CREATE TEMPORARY TABLE TT_GESTION_CANALES AS
SELECT ... FROM PROD_MAESTROBI.DBO.EXT_MC_GESTIONCANALES ...;
```

### Example 6: READ keeps PROD, even inside an INSERT-SELECT

```sql
-- PROD
INSERT INTO PROD_MAESTROBI.DBO.EFE_MC_CREDITOSNOASIGNADOS
SELECT a.*, b.col
FROM PROD_MAESTROBI.DBO.A a
JOIN PROD_MAESTROBI.DBO.B b ON a.id = b.id;

-- DESA (EFE in manifest → suffix + prefix; reads stay PROD)
INSERT INTO DESA_MAESTROBI.DBO.EFE_MC_CREDITOSNOASIGNADOS_35145
SELECT a.*, b.col
FROM PROD_MAESTROBI.DBO.A a
JOIN PROD_MAESTROBI.DBO.B b ON a.id = b.id;
```

### Example 7: pre-existing DESA read stays DESA

Sometimes a production SP already reads from `DESA_*` (a developer forgot to fix it, or it was an intentional dev-staging reference). These stay untouched.

```sql
-- PROD
SELECT * FROM DESA_MODELOS.DBO.UMD_FED_DETALLEBASEMASIVAS;

-- DESA clone
SELECT * FROM DESA_MODELOS.DBO.UMD_FED_DETALLEBASEMASIVAS;   -- unchanged
```

## Side effects — special treatment

Side effects (email senders, external notifications, audit inserts, downstream triggers) are handled by consulting `docs/side-effects-catalog.md`. The catalog maps patterns to actions:

- `comment_out` — the statement is wrapped in a comment in the clone.
- `redirect_to(<arg>)` — for email-sending side effects, the recipient is replaced with `<arg>`.
- `keep` — the statement is preserved (safe audit tables, inocuous logs).

A `manifest.yaml` may provide `side_effects_overrides` to alter the default action for a single REN (e.g., redirect all emails to the developer's personal inbox to verify a visual change).

If `migrator/` finds a CALL or INSERT that matches no catalog entry and looks suspicious (name contains `MAIL`, `NOTIF`, `SEND`, or targets a table with `_LOG` / `_AUDIT` suffix), it stops and asks the human. The answer is persisted to the catalog.

## What `migrator/` does not do

- It does not modify the REN's requested business logic. That is phase 7 (edits), a separate concern.
- It does not validate that the cloned procedure still compiles. That is enforced by `nz_clone_procedure` in `nz-mcp`, which runs the DDL through the sql_guard NZPLSQL validator before execution.
- It does not run the clone. That is phase 6 (baseline) / 8 (comparison) in `tester/`.
