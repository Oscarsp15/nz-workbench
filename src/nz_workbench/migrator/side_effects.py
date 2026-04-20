"""Side-effects catalog: patterns → actions, with per-REN overrides."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Action = Literal["comment_out", "redirect_to", "keep"]


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One row of docs/side-effects-catalog.md."""

    pattern: str
    default_action: Action
    default_arg: str | None
    notes: str


@dataclass(frozen=True, slots=True)
class AppliedAction:
    """Decision the migrator made for a specific statement in a specific SP."""

    pattern: str
    action: Action
    arg: str | None
    reason: str
    line_from: int
    line_to: int


def load_catalog(path: Path) -> list[CatalogEntry]:
    """Parse docs/side-effects-catalog.md into structured entries."""
    raise NotImplementedError


def decide(
    statement_text: str,
    *,
    catalog: list[CatalogEntry],
    overrides: list[CatalogEntry],
) -> AppliedAction | None:
    """Match a statement against catalog + overrides; return the action or None."""
    raise NotImplementedError


__all__ = ["Action", "AppliedAction", "CatalogEntry", "decide", "load_catalog"]
