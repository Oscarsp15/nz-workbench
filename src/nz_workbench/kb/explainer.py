"""Generate pedagogical mappings of procedures (``nz-workbench explain``).

Uses Claude (token-bound, separate from raw indexing) to produce block-by-block
explanations that are stored in ``docs/procedures/<SP>.md`` under "IA mapping".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Explanation:
    """Structured output of a pedagogical mapping."""

    purpose: str
    architecture_blocks: list[str]
    external_reads: list[str]
    external_writes: list[str]
    calls: list[str]
    side_effects_detected: list[str]


def explain_procedure(database: str, schema: str, procedure: str) -> Explanation:
    """Produce a human-readable mapping for the procedure.

    Placeholder — full implementation will call an LLM (Claude) with the DDL plus
    human-authored notes from ``docs/procedures/<SP>.md`` (if present), then write
    the output back to the auto-managed sections of that same file.
    """
    raise NotImplementedError


__all__ = ["Explanation", "explain_procedure"]
