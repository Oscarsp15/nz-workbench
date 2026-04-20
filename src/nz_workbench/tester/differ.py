"""Table-diff primitives used by baseline and comparison."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TableDiff:
    """Row-level and aggregate comparison of two tables."""

    left_rows: int
    right_rows: int
    delta: int
    delta_pct: float
    key_columns: list[str]
    sample_different: list[dict[str, object]]


def diff_tables(
    left_qualified: str,
    right_qualified: str,
    *,
    key_columns: list[str],
    max_sample: int = 20,
) -> TableDiff:
    """Diff two fully qualified Netezza tables by natural key.

    Placeholder — executes SELECTs via nz-mcp and returns aggregates + a small sample.
    """
    raise NotImplementedError


__all__ = ["TableDiff", "diff_tables"]
