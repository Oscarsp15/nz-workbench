from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from nz_workbench.kb.embedder import SentenceTransformerEmbedder, make_embedder


class _FakeModel:
    def __init__(self, on_encode: Callable[[int], None] | None = None) -> None:
        self._on_encode = on_encode

    def encode(self, texts: list[str], **_: Any) -> NDArray[np.float64]:
        if self._on_encode is not None:
            self._on_encode(len(texts))
        return np.zeros((len(texts), 1024), dtype=float)


@pytest.mark.unit
def test_lazy_load(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[int] = []

    def fake_st_ctor(_name: str, device: str) -> _FakeModel:
        created.append(1)
        assert device == "cpu"
        return _FakeModel()

    monkeypatch.setattr("nz_workbench.kb.embedder._resolve_device", lambda: "cpu")
    monkeypatch.setattr("nz_workbench.kb.embedder._SENTENCE_TRANSFORMER", fake_st_ctor)

    emb = SentenceTransformerEmbedder(model_name="BAAI/bge-m3")
    assert created == []
    out = emb.embed(["a", "b"])
    assert created == [1]
    assert len(out) == 2
    assert len(out[0]) == 1024


@pytest.mark.unit
def test_batch_size_env(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def on_encode(n: int) -> None:
        calls.append(n)

    def fake_st_ctor(_name: str, device: str) -> _FakeModel:
        assert device == "cpu"
        return _FakeModel(on_encode=on_encode)

    monkeypatch.setenv("NZ_WORKBENCH_EMBED_BATCH", "1")
    monkeypatch.setattr("nz_workbench.kb.embedder._resolve_device", lambda: "cpu")
    monkeypatch.setattr("nz_workbench.kb.embedder._SENTENCE_TRANSFORMER", fake_st_ctor)

    emb = make_embedder("BAAI/bge-m3")
    out = emb.embed(["a", "b", "c"])
    assert len(out) == 3
    assert calls == [1, 1, 1]

    os.environ.pop("NZ_WORKBENCH_EMBED_BATCH", None)
