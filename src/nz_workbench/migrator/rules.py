"""PROD→DESA rewrite rules (see docs/architecture/prod-desa-rules.md)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RefKind = Literal["read", "write", "call"]


@dataclass(frozen=True, slots=True)
class RewriteRule:
    """The decision of what to do with one reference inside a cloned procedure."""

    ref_kind: RefKind
    original_database: str
    original_schema: str
    original_object: str
    target_database: str
    target_schema: str
    target_object: str
    reason: str   # human-readable why this rule applied


@dataclass(frozen=True, slots=True)
class ManifestContext:
    """The parts of the REN manifest the rule engine needs to decide rewrites."""

    prod_to_desa_prefix_map: dict[str, str]   # e.g. "PROD_MAESTROBI" -> "DESA_MAESTROBI"
    tables_to_clone: frozenset[str]           # fully qualified names
    procedures_to_call_with_suffix: frozenset[str]
    suffix: str                                # "_35145"


def rewrite_reference(
    ref_kind: RefKind,
    database: str,
    schema: str,
    obj: str,
    ctx: ManifestContext,
) -> RewriteRule:
    """Return the rewrite rule for a single reference.

    Placeholder — full implementation will follow the table in
    ``docs/architecture/prod-desa-rules.md``.
    """
    raise NotImplementedError


__all__ = ["RefKind", "RewriteRule", "ManifestContext", "rewrite_reference"]
