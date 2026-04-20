"""Read/write helpers for docs/procedures/<SP>.md with section-ownership rules.

Four sections with strict ownership (see AGENTS.md § 7):
- "Metadata (auto)" — IA maintains.
- "IA mapping (auto)" — IA maintains.
- "Notas humanas (manual)" — IA NEVER writes here.
- "Change log (auto)" — IA appends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ProcedureDoc:
    """In-memory representation of a ``docs/procedures/<SP>.md`` file."""

    sp_name: str
    metadata_md: str = ""
    ia_mapping_md: str = ""
    notas_humanas_md: str = ""
    change_log_entries: list[str] = field(default_factory=list)


def read_doc(path: Path) -> ProcedureDoc:
    """Parse an existing file into structured sections."""
    raise NotImplementedError


def write_doc(path: Path, doc: ProcedureDoc) -> None:
    """Serialize back to disk preserving the "Notas humanas" section verbatim."""
    raise NotImplementedError


def append_change_log(path: Path, entry_md: str) -> None:
    """Convenience: add a "Change log (auto)" entry without rewriting other sections."""
    raise NotImplementedError


__all__ = ["ProcedureDoc", "append_change_log", "read_doc", "write_doc"]
