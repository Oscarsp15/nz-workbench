# Git workflow

Same rigor as `nz-mcp`. CI enforces every rule below; PRs that fail these checks do not merge.

## 1. Branch names

Regex validated in CI:

```
^(feat|fix|chore|refactor|docs|test|security|perf|build|ci|ren)/\d+-[a-z0-9-]+$
```

Examples:
- `feat/12-kb-bootstrap`
- `fix/34-side-effects-redirect`
- `ren/35145-asig-desembolso-canal`

The `ren/` prefix is specific to this project and identifies branches that carry REN work. The number after the slash is the REN number (not a GitHub issue number) when using `ren/`, or the GitHub issue number otherwise.

## 2. Commit subjects

Regex:

```
^(feat|fix|chore|refactor|docs|test|security|perf|build|ci|ren)(\([a-z0-9-]+\))?(!)?: [^\s].{0,71}$
```

Rules:
- Type is mandatory and from the allowed list.
- Scope is optional; when present, must match `[a-z0-9-]+` — no underscores, no commas, no ellipsis.
- `:` + single space + description.
- Description is in Spanish, imperative form, lowercase first letter, no trailing period.
- Total subject length ≤ 72 characters.
- Unicode ellipsis `…` (U+2026) is forbidden — causes CI rejection.
- One intention per commit. If you would write "and" in the subject, split.

Examples:
- `feat(kb): bootstrap indexa 6300 procedures en 2 horas`
- `fix(migrator): preserva DESA existente en reads`
- `ren(35145): aplica change points 1-4`

## 3. Conventional commit types

| Type | When to use |
|---|---|
| `feat` | A new capability (CLI command, module, behavior) |
| `fix` | Correct a bug |
| `refactor` | Change internal structure without altering behavior |
| `test` | Add or update tests only |
| `docs` | Documentation only (README, docs/, docstrings) |
| `chore` | Housekeeping: deps bump, formatter run, CI tweak |
| `security` | Security-relevant change (never silent, always documented) |
| `perf` | Performance improvement with measurement |
| `build` | Build system or external dependencies |
| `ci` | CI/CD pipeline |
| `ren` | Work scoped to a specific REN folder |

## 4. PR titles

Same regex as commit subjects. The title is canonically the subject of the squash commit that lands on `main`.

## 5. PR body

The body must include the five headings validated by `scripts/check_pr_body.py`:

- `## ¿Qué cambia?`
- `## Issue relacionado`
- `## Acción según AGENTS.md`
- `## Auditoría pre-merge`
- `## Validación humana`

See `.github/PULL_REQUEST_TEMPLATE.md` for the full template. The issue line must contain `Closes #<n>` or `Refs #<n>`.

## 6. Merge policy

- Squash merge only. The PR title becomes the commit subject.
- Branches are auto-deleted after merge.
- No force-push to `main`. Ever.
- No `--amend` of commits already on `main`.
- Pre-commit hooks must pass locally before pushing. Never bypass with `--no-verify`.

## 7. Labels

| Label | Purpose |
|---|---|
| `type/bug`, `type/feature`, `type/chore`, `type/refactor`, `type/docs`, `type/test`, `type/security`, `type/ren` | Category |
| `priority/P0`, `priority/P1`, `priority/P2`, `priority/P3` | Urgency |
| `area/kb`, `area/analyzer`, `area/migrator`, `area/tester`, `area/docs`, `area/ci`, `area/cli`, `area/mcp-server` | Module |
| `complexity/S`, `complexity/M`, `complexity/L`, `complexity/XL` | Effort estimate |
| `ai-ready` | Can be implemented by an AI with the issue alone |
| `needs-spec` | Requires human refinement before implementing |
| `blocked` | Depends on another issue |
| `ren` | Work that originates from a REN |

## 8. Branch lifecycle

```
main                 ← protected, never force-pushed
  │
  ├── feat/12-…      ← created from main
  │                    opened PR → CI → auditor review → squash merge → auto-delete
  │
  ├── ren/35145-…    ← per-REN work
  │                    tests, diffs, docs committed → squash merge
```

## 9. Release tags

Semantic versioning: `v<major>.<minor>.<patch>`. Tags are created manually when a milestone is reached (no automatic release on every merge).
