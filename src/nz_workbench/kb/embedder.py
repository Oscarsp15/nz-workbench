"""BGE-M3 embedder wrapper.

Loads ``BAAI/bge-m3`` lazily via ``sentence-transformers`` and exposes a simple
``embed(texts: list[str]) -> list[list[float]]`` API.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Final, Protocol, cast

import structlog

_log = structlog.get_logger(__name__)

_ENV_BATCH: Final[str] = "NZ_WORKBENCH_EMBED_BATCH"
_ENV_DEVICE: Final[str] = "NZ_WORKBENCH_EMBED_DEVICE"  # "cpu" (default) | "cuda"
_EXPECTED_DIM: Final[int] = 1024

_TORCH: Any | None = None
_imported_torch: Any
try:
    import torch as _imported_torch
except Exception:  # pragma: no cover
    _imported_torch = None
else:
    _TORCH = _imported_torch

_SENTENCE_TRANSFORMER: Any | None = None
_ImportedSentenceTransformer: Any
try:
    from sentence_transformers import SentenceTransformer as _ImportedSentenceTransformer
except Exception:  # pragma: no cover
    _ImportedSentenceTransformer = None
else:
    _SENTENCE_TRANSFORMER = _ImportedSentenceTransformer


class Embedder(Protocol):
    """Minimal embedder contract used across the KB module."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one 1024-dim vector per input text."""
        ...


def _batch_size() -> int:
    raw = os.environ.get(_ENV_BATCH, "32")
    try:
        value = int(raw)
    except ValueError:
        return 32
    return max(1, min(value, 512))


def _resolve_device() -> str:
    requested = os.environ.get(_ENV_DEVICE, "cpu").strip().lower()
    if requested not in {"cpu", "cuda"}:
        requested = "cpu"

    if requested == "cuda":
        if _TORCH is None:
            return "cpu"
        return "cuda" if bool(_TORCH.cuda.is_available()) else "cpu"

    return "cpu"


@dataclass(slots=True)
class SentenceTransformerEmbedder:
    """Lazy-loaded sentence-transformers model wrapper."""

    model_name: str
    _model: object | None = None
    _device: str = "cpu"

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        self._device = _resolve_device()
        t0 = time.perf_counter()
        if _SENTENCE_TRANSFORMER is None:  # pragma: no cover
            raise RuntimeError("sentence-transformers is required to embed procedure chunks")

        self._model = _SENTENCE_TRANSFORMER(self.model_name, device=self._device)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        _log.info(
            "embedder_loaded",
            model_name=self.model_name,
            device=self._device,
            duration_ms=round(duration_ms, 2),
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        self._ensure_loaded()
        if self._model is None:  # pragma: no cover
            raise RuntimeError("embedder model failed to load")

        batch = _batch_size()
        vectors: list[list[float]] = []

        for start in range(0, len(texts), batch):
            end = min(start + batch, len(texts))
            chunk = texts[start:end]
            t0 = time.perf_counter()

            # SentenceTransformer.encode returns np.ndarray or list depending on config.
            model = cast(Any, self._model)
            out = model.encode(
                chunk,
                batch_size=batch,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )

            duration_ms = (time.perf_counter() - t0) * 1000.0
            _log.info(
                "embedder_batch_done",
                n_texts=len(chunk),
                duration_ms=round(duration_ms, 2),
            )

            # Numpy array supports iteration returning vectors.
            for vec in out:
                as_list = [float(x) for x in vec]
                if len(as_list) != _EXPECTED_DIM:
                    raise ValueError(
                        f"unexpected embedding dim: {len(as_list)} (expected {_EXPECTED_DIM})"
                    )
                vectors.append(as_list)

        return vectors


def make_embedder(model_name: str = "BAAI/bge-m3") -> Embedder:
    """Factory for the default embedder. Loads the model on first use."""

    return SentenceTransformerEmbedder(model_name=model_name)


__all__ = ["Embedder", "SentenceTransformerEmbedder", "make_embedder"]
