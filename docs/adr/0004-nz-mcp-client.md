# ADR 0004 — nz-mcp as the only Netezza access path

- **Date**: 2026-04-19
- **Status**: accepted
- **Decided by**: Tech Lead + human validation via PR

## Context

This project needs to list procedures, fetch DDLs, run baseline and comparison queries, and invoke `nz_clone_procedure`. Two options:

1. Depend on `nz-mcp` as an MCP subprocess and call its tools.
2. Re-implement Netezza access (nzpy, sql_guard, identifier validation, profile handling) inside this repo.

## Decision

**Option 1. `nz-mcp` is the only Netezza access path.** `nz-workbench` launches `nz-mcp serve` as a subprocess, talks to it over stdio JSON-RPC, and never touches `nzpy` or a SQL driver directly.

## Consequences

- **Positive**:
  - Zero duplication of connection logic, sql_guard, identifier validation, keyring, cross-DB rendering, NZPLSQL parsing.
  - Any security fix or feature added to `nz-mcp` is inherited immediately.
  - Clear separation of concerns: `nz-mcp` handles Netezza, `nz-workbench` handles workflow.
  - If the public catalog evolves (new tools like `nz_analyze_procedure_references`), we simply consume them.
- **Negative**:
  - Extra latency per tool call (JSON-RPC over stdio is fast, ~1-2 ms overhead per call).
  - A bug in `nz-mcp` can block us. Mitigation: the dual-AI audit cycle on `nz-mcp` has historically caught bugs within hours.
  - Requires `nz-mcp` to be installed on the developer's machine (pipx or venv).
- **Neutral**:
  - We are coupled to the MCP protocol. Acceptable — MCP is the native transport for Claude tooling.

## Alternatives considered

- **Fork `nz-mcp` internals into this project**: rejected. Duplicates 5,000+ LoC of security-critical code that must be kept in sync. Effort outweighs the latency benefit.
- **Direct nzpy usage with a thin wrapper**: rejected. Loses sql_guard and identifier validation. Security regression.
- **SQL generation only, no execution (produce scripts, run by hand)**: rejected. Kills the baseline and comparison automation that `tester/` depends on.

## Operational notes

`nz-workbench` expects `nz-mcp` available as either:

- An executable on `PATH` named `nz-mcp` (installed via `pipx install nz-mcp` or from source).
- A configurable path set in `config.py` / env var `NZ_MCP_BIN`.

The MCP subprocess is started lazily when the first tool call is made and reused for the lifetime of the `nz-workbench` process.
