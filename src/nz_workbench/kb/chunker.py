"""NZPLSQL body chunking for indexing.

Splits a procedure body into ~400-token chunks with 50-token overlap, respecting
``DECLARE`` / ``BEGIN`` / ``END LOOP`` boundaries and never breaking inside a string
literal or comment block.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

TARGET_TOKENS: Final[int] = 400
OVERLAP_TOKENS: Final[int] = 50


@dataclass(frozen=True, slots=True)
class Chunk:
    """One chunk of an NZPLSQL body, ready to embed."""

    text: str
    line_from: int
    line_to: int
    section_hint: str  # "header" | "declare" | "body" | "exception"


def chunk(body: str) -> list[Chunk]:
    """Return the chunks of a procedure body.

    Placeholder — full implementation will:
    - Use BGE-M3 tokenizer to count tokens.
    - Respect NZPLSQL structural markers (see ``nz-mcp``'s nzplsql_parser).
    - Emit overlapping chunks to preserve context across boundaries.
    """
    raise NotImplementedError


__all__ = ["Chunk", "chunk", "TARGET_TOKENS", "OVERLAP_TOKENS"]
