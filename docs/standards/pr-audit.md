# PR audit — seven dimensions

Every PR is reviewed by the auditor AI against the same seven dimensions before merge. This mirrors `nz-mcp` and catches both mechanical and policy issues.

## 1. Contract and compatibility

- If the PR touches the CLI, MCP server, or KB schema, `docs/architecture/` and `CHANGELOG.md` are updated in the same PR with a bilingual entry.
- No unexpected breaking changes. If breaking, `CHANGELOG.md` entry is under `Changed` with migration notes.
- New tools / CLI commands are documented in `README.md` or the relevant docs.

## 2. Security

- No credentials, profiles, or REN business content committed.
- All SQL that touches Netezza goes through `nz-mcp` (never direct `nzpy` calls from this repo).
- No `except Exception` without re-raise as a typed error.
- If the PR modifies the migrator rules, the side-effects catalog, or the sql_guard bridge, the auditor checks that existing clones are still safe.

## 3. Maintainability and design

- The PR touches only the files in scope, or documents why not.
- No new abstraction added without three real usages.
- No new dependency without an ADR under `docs/adr/`.
- Functions under 50 LoC, up to 4 parameters. Classes focused on one responsibility.
- One intention per PR.
- PR under 400 LoC excluding tests and docs, or justified.

## 4. Tests

- New behavior has tests.
- `pytest -m "not integration"` passes locally.
- Coverage ≥ 85% globally, no regression in touched files.
- No `pytest.skip` or `xfail` without a linked issue.

## 5. Typing and style

- `ruff check .` and `ruff format --check .` clean.
- `mypy --strict` clean in touched modules.
- No `Any` on public surfaces without justification.
- No `except Exception` without re-raise.

## 6. Documentation

- Public API changes → `docs/architecture/`, `README.md` updated.
- Behavior changes → `CHANGELOG.md` bilingual entry.
- Architectural decisions → new ADR under `docs/adr/`.
- User-facing messages → ES and EN strings provided.

## 7. Language and form

- PR title in Spanish, conventional-commit format.
- Branch name matches the regex.
- Commits in Spanish, conventional-commit, lowercase first letter, no ellipsis.
- Code and inline comments in English.
- PR body has the five required `##` headings.

## Zero-guess enforcement

In addition to the seven dimensions, the auditor enforces the "AI never guesses" principle from `AGENTS.md` § 2.2:

- If the PR adds code that makes a decision based on a threshold, a pattern, or a default, the auditor checks that the threshold / pattern / default is either explicitly documented in a config file or asked from the user at runtime.
- If the PR includes a commit whose description says the AI "assumed", "inferred", or "defaulted" without a reference to where that default is configurable, the PR is blocked until the assumption is either eliminated or exposed as configuration.

## Merge gate

A PR merges when:

1. All seven dimensions are green.
2. Zero-guess check passes.
3. CI is green.
4. The human (Oscar) has approved, or the PR was opened directly by Oscar and the auditor AI has approved.

The auditor AI never merges a PR it authored.
