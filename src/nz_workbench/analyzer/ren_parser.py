"""Extract entities and change points from a REN source document."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EntityMention:
    """A table, column, code, or procedure name mentioned in the REN."""

    kind: str   # "table" | "column" | "procedure" | "code" | "threshold"
    value: str
    context: str   # the surrounding text from the REN


@dataclass(frozen=True, slots=True)
class ChangePointDraft:
    """A candidate change point extracted from the REN (pre-localization)."""

    summary: str
    ren_reference: str   # where in source.md this was described
    entities: list[EntityMention] = field(default_factory=list)


def parse_ren(source_markdown: str) -> list[ChangePointDraft]:
    """Return a list of change-point drafts extracted from the REN text.

    Placeholder — full implementation will use a mix of regex + LLM to identify:
    - Tables, columns, codes, literals, thresholds.
    - Requested operation (add / remove / modify).
    - Conditional scopes (e.g. "only for 31-day months").
    """
    raise NotImplementedError


__all__ = ["EntityMention", "ChangePointDraft", "parse_ren"]
