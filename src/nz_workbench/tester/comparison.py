"""Comparison test: run modified clone; report diffs vs PROD grouped by dimension."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DimensionDiff:
    """Aggregated diff along one dimension (e.g. CANAL)."""

    dimension: str
    rows: list[tuple[str, int, int]]   # (value, prod_count, desa_count)


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Outcome of the comparison after edits are applied."""

    prod_total: int
    desa_total: int
    dimensions: list[DimensionDiff]
    sample_differing_rows: list[dict[str, object]]
    expected_effects_observed: list[str]
    unexpected_effects: list[str]
    report_path: Path


def run_comparison(ren_folder: Path) -> ComparisonResult:
    """Execute the comparison phase after all change points are applied.

    Placeholder — implementation will:
    1. Run the modified clone with test parameters.
    2. Query every final output table from PROD and DESA.
    3. Aggregate by user-specified or inferred dimensions.
    4. Correlate with change_points in analysis.yaml to flag expected vs unexpected.
    """
    raise NotImplementedError


__all__ = ["DimensionDiff", "ComparisonResult", "run_comparison"]
