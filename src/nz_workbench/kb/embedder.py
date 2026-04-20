"""BGE-M3 embedder wrapper.

Loads ``BAAI/bge-m3`` lazily via ``sentence-transformers`` and exposes a simple
``embed(texts: list[str]) -> list[list[float]]`` API.
"""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    """Minimal embedder contract used across the KB module."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one 1024-dim vector per input text."""
        ...


def make_embedder(model_name: str = "BAAI/bge-m3") -> Embedder:
    """Factory for the default embedder. Loads the model on first use."""
    raise NotImplementedError


__all__ = ["Embedder", "make_embedder"]
