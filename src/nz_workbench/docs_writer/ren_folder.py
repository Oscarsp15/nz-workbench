"""Create and populate a ren/REN_<N>/ folder from the _TEMPLATE."""

from __future__ import annotations

from pathlib import Path


def scaffold_ren_folder(project_root: Path, ren_number: int) -> Path:
    """Copy ``ren/_TEMPLATE/`` to ``ren/REN_<N>/`` and return the new path.

    Fails if the target folder already exists (never overwrite a REN in progress).
    """
    raise NotImplementedError


def write_summary(ren_folder: Path, *, status: str, links: dict[str, Path]) -> None:
    """Write ``summary.md`` at phase 9."""
    raise NotImplementedError


__all__ = ["scaffold_ren_folder", "write_summary"]
