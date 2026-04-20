"""Orchestrates the full clone phase: load manifest → rewrite per SP → call nz-mcp."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MigrateReport:
    """Outcome of running ``nz-workbench migrate`` on a REN folder."""

    dry_run: bool
    procedures_cloned: int
    procedures_skipped: int
    warnings: list[str]
    diff_files: list[Path]


def migrate(ren_folder: Path, *, dry_run: bool = True) -> MigrateReport:
    """Execute the clone phase for the REN manifest at ``ren_folder/manifest.yaml``.

    Placeholder — full implementation will:
    1. Load manifest + side-effects catalog + overrides.
    2. For each source SP, fetch DDL via nz-mcp.
    3. Derive the transformation list (prefix + suffix + side-effects).
    4. Invoke ``nz_clone_procedure`` from nz-mcp with that list.
    5. Save per-SP DDL diffs under ``ren_folder/diffs/baseline-cloned/``.
    """
    raise NotImplementedError


__all__ = ["MigrateReport", "migrate"]
