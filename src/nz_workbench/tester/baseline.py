"""Baseline test: run original PROD and unmodified clone; confirm output parity."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BaselineResult:
    """Outcome of the baseline run."""

    passed: bool
    tables_compared: int
    tables_differ: list[str]
    details_report_path: Path


def run_baseline(ren_folder: Path) -> BaselineResult:
    """Execute baseline: PROD SP vs unmodified DESA clone.

    Placeholder — uses nz-mcp CALL to run both SPs with the test parameters
    from ``manifest.yaml`` and compares every final output table.
    """
    raise NotImplementedError


__all__ = ["BaselineResult", "run_baseline"]
