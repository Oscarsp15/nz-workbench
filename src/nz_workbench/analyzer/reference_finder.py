"""Locate candidate SPs and sections for each change point (structural + semantic)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candidate:
    """A possible (procedure, section) match for a change point."""

    database: str
    schema: str
    procedure: str
    signature: str
    line_from: int
    line_to: int
    confidence: float  # 0.0 - 1.0
    matched_via: str  # "structural" | "semantic" | "hybrid"


def find_candidates(*_args: object, **_kwargs: object) -> list[Candidate]:
    """Return candidate matches for a change point, sorted by confidence.

    Placeholder — combines ``kb.search_hybrid`` with structural queries against
    ``metadata_store`` (e.g. "SPs that write to table X").
    """
    raise NotImplementedError


__all__ = ["Candidate", "find_candidates"]
