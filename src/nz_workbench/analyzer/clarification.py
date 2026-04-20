"""Clarification agent: produces the list of questions the human must answer.

Enforces the "AI never guesses" principle from AGENTS.md § 2.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AmbiguityKind = Literal[
    "missing_schema_qualifier",
    "numeric_threshold_unparametrized",
    "no_literal_match_in_candidate_sp",
    "multiple_candidate_sections",
    "uncatalogued_side_effect",
    "new_object_without_spec",
]


@dataclass(frozen=True, slots=True)
class Clarification:
    """One question for the human."""

    ambiguity: AmbiguityKind
    question: str
    context: str
    candidates: list[str]   # if applicable, possible answers with confidence
    change_point_id: int | None = None


def derive_clarifications(*_args: object, **_kwargs: object) -> list[Clarification]:
    """Return all clarifications needed before the REN can proceed.

    Placeholder — full implementation will examine the change-point drafts plus
    the KB search results and emit one Clarification per detected ambiguity.
    """
    raise NotImplementedError


__all__ = ["AmbiguityKind", "Clarification", "derive_clarifications"]
