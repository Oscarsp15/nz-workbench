from __future__ import annotations

import pytest

from nz_workbench.kb import embedder


@pytest.mark.unit
def test_batch_size_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NZ_WORKBENCH_EMBED_BATCH", "nope")
    assert embedder._batch_size() == 32

    monkeypatch.setenv("NZ_WORKBENCH_EMBED_BATCH", "0")
    assert embedder._batch_size() == 1

    monkeypatch.setenv("NZ_WORKBENCH_EMBED_BATCH", "9999")
    assert embedder._batch_size() == 512


@pytest.mark.unit
def test_resolve_device_falls_back_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NZ_WORKBENCH_EMBED_DEVICE", "wat")
    assert embedder._resolve_device() == "cpu"

    monkeypatch.setenv("NZ_WORKBENCH_EMBED_DEVICE", "cuda")
    original = embedder._TORCH
    embedder._TORCH = None
    try:
        assert embedder._resolve_device() == "cpu"
    finally:
        embedder._TORCH = original


@pytest.mark.unit
def test_embedder_raises_if_sentence_transformers_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    original = embedder._SENTENCE_TRANSFORMER
    embedder._SENTENCE_TRANSFORMER = None
    try:
        e = embedder.SentenceTransformerEmbedder(model_name="BAAI/bge-m3")
        with pytest.raises(RuntimeError):
            e.embed(["x"])
    finally:
        embedder._SENTENCE_TRANSFORMER = original
