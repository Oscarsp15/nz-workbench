# Architecture decision records

An ADR captures a single architectural decision, its context, and its consequences. Any change that affects module boundaries, runtime dependencies, or external integrations must be preceded by an ADR.

## Index

| # | Title | Status | Date |
|---|---|---|---|
| 0001 | [Python 3.11 + typer as the stack](0001-python-stack.md) | accepted | 2026-04-19 |
| 0002 | [Chroma as the local vector store](0002-chroma-local-vector-db.md) | accepted | 2026-04-19 |
| 0003 | [BGE-M3 as the embedding model](0003-bge-m3-embedder.md) | accepted | 2026-04-19 |
| 0004 | [nz-mcp as the only Netezza access path](0004-nz-mcp-client.md) | accepted | 2026-04-19 |

## Template

```markdown
# ADR NNNN — <short title>

- **Date**: YYYY-MM-DD
- **Status**: proposed | accepted | superseded by ADR NNNN | deprecated
- **Decided by**: <role> + human validation via PR

## Context

What is the problem? What is the environment?

## Decision

What did we decide? State it in one paragraph.

## Consequences

- **Positive**: …
- **Negative**: …
- **Neutral / trade-offs**: …

## Alternatives considered

- Alt A: why rejected
- Alt B: why rejected
```
