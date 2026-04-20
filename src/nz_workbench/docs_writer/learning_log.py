"""Append-only writer for docs/learning-log.md."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LearningEntry:
    """One entry in the learning log."""

    date: str      # YYYY-MM-DD
    title: str
    ren: int | None
    what_i_learned: list[str]
    why_it_matters: str


def append_entry(log_path: Path, entry: LearningEntry) -> None:
    """Append a new entry at the end of the learning log file."""
    raise NotImplementedError


__all__ = ["LearningEntry", "append_entry"]
