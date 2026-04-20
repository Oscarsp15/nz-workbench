"""REN manifest schema and load/validate helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProcedureIdentity(BaseModel):
    """Fully qualified procedure name."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    database: str = Field(min_length=1, max_length=128)
    schema_: str = Field(min_length=1, max_length=128, alias="schema")
    name: str = Field(min_length=1, max_length=128)
    signature: str | None = Field(default=None, max_length=2048)


class ProcedureMigration(BaseModel):
    """One source→target procedure in the manifest."""

    model_config = ConfigDict(extra="forbid")

    source: ProcedureIdentity
    target: ProcedureIdentity


class SideEffectOverride(BaseModel):
    """Per-REN override of an entry from docs/side-effects-catalog.md."""

    model_config = ConfigDict(extra="forbid")

    pattern: str
    action: Literal["comment_out", "redirect_to", "keep"]
    arg: str | None = None
    reason: str


class Manifest(BaseModel):
    """Full REN manifest."""

    model_config = ConfigDict(extra="forbid")

    ren: int
    suffix: str
    procedures: list[ProcedureMigration] = Field(min_length=1)
    tables_to_clone: list[str] = Field(default_factory=list)
    procedures_to_call_with_suffix: list[str] = Field(default_factory=list)
    side_effects_overrides: list[SideEffectOverride] = Field(default_factory=list)
    test_parameters: dict[str, str] = Field(default_factory=dict)


def load_manifest(path: Path) -> Manifest:
    """Read ``manifest.yaml`` from the given REN folder and validate it."""
    raise NotImplementedError


__all__ = [
    "Manifest",
    "ProcedureIdentity",
    "ProcedureMigration",
    "SideEffectOverride",
    "load_manifest",
]
