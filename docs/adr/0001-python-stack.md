# ADR 0001 — Python 3.11 + typer as the stack

- **Date**: 2026-04-19
- **Status**: accepted
- **Decided by**: Tech Lead + human validation via PR

## Context

`nz-workbench` must run locally on developer machines, interact with `nz-mcp` as an MCP client, drive Chroma and BGE-M3 for the knowledge base, and expose a CLI plus an MCP server. The team already uses Python for `nz-mcp` and for day-to-day Netezza work.

## Decision

- Language: **Python 3.11+**. 3.11 is the minimum because it is the lowest supported version of `nz-mcp` and gives us `StrEnum`, `tomllib`, better `typing.Self` ergonomics.
- CLI framework: **typer** ≥ 0.15. Same version pinned by `nz-mcp` (resolves the typer/click 8.2 incompatibility documented in `nz-mcp` issue #69).
- Data modeling: **pydantic v2**. Same as `nz-mcp`.
- Logging: **structlog** routed to stderr via the same helper pattern `nz-mcp` uses (ADR shared in ethos with `nz-mcp` issue #86).
- Test runner: **pytest** with `pytest-cov`, `hypothesis` for property tests.

## Consequences

- **Positive**: team is already fluent. Full interop with `nz-mcp` since they share the runtime and versions.
- **Negative**: Python CPU performance is lower than Rust/Go. For the parser and the BGE-M3 inference this is acceptable (CPU time dominated by the embedder, not glue code).
- **Neutral**: `sentence-transformers` is a large dep (~500 MB with model weights). Accepted as cost of local inference.

## Alternatives considered

- **Rust** for the migrator + parser, Python for CLI: faster but two languages in a two-person project is overkill.
- **Click** directly (no typer): loses the declarative type-based CLI that makes `typer` pleasant. Not worth the verbosity.
- **Python 3.10**: missing `StrEnum` and `tomllib`. Would force backports.
