from __future__ import annotations

import math
from itertools import pairwise

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from nz_workbench.kb import chunker


def _wc_tokens(text: str) -> int:
    return len([t for t in text.split() if t])


def _reconstruct_with_word_overlap(chunks: list[chunker.Chunk]) -> str:
    if not chunks:
        return ""
    out_words: list[str] = []
    for idx, c in enumerate(chunks):
        words = c.text.split()
        if idx == 0:
            out_words.extend(words)
        else:
            out_words.extend(words[chunker.OVERLAP_TOKENS :])
    return " ".join(out_words)


def _reconstruct_by_string_overlap(chunks: list[chunker.Chunk], max_overlap: int = 5000) -> str:
    if not chunks:
        return ""
    acc = chunks[0].text
    for c in chunks[1:]:
        nxt = c.text
        window = acc[-max_overlap:] if len(acc) > max_overlap else acc
        max_k = min(len(window), len(nxt))
        merged = False
        for k in range(max_k, 0, -1):
            if window[-k:] == nxt[:k]:
                acc += nxt[k:]
                merged = True
                break
        if not merged:
            acc += nxt
    return acc


@pytest.mark.unit
def test_body_one_line_one_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunker, "_count_tokens", _wc_tokens)
    body = "BEGIN SELECT 1; END;"
    chunks = chunker.chunk(body)
    assert len(chunks) == 1
    assert chunks[0].line_from == 1
    assert chunks[0].line_to == 1


@pytest.mark.unit
def test_large_body_chunks_have_overlap_and_reasonable_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chunker, "_count_tokens", _wc_tokens)
    words = [f"w{i}" for i in range(2000)]
    # Create many statement boundaries.
    body = "BEGIN\n" + " ".join(words[:1000]) + ";\n" + " ".join(words[1000:]) + ";\nEND;\n"
    chunks = chunker.chunk(body)
    assert len(chunks) >= 2
    # Word-count proxy: allow some slack because boundaries are coarse.
    for c in chunks:
        assert _wc_tokens(c.text) <= 450

    # Rough overlap: consecutive chunks should share at least some words.
    for a, b in pairwise(chunks):
        a_tail = set(a.text.split()[-chunker.OVERLAP_TOKENS :])
        b_head = set(b.text.split()[: chunker.OVERLAP_TOKENS])
        assert a_tail.intersection(b_head)


@pytest.mark.unit
def test_does_not_split_inside_string_literal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunker, "_count_tokens", _wc_tokens)
    body = "BEGIN\n  x := ';'; y := 1;\nEND;\n"
    chunks = chunker.chunk(body)
    joined = "".join(c.text for c in chunks)
    assert "x := ';';" in joined


@pytest.mark.unit
def test_does_not_split_inside_block_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunker, "_count_tokens", _wc_tokens)
    body = "BEGIN\n  /* comment ; still comment */\n  y := 1;\nEND;\n"
    chunks = chunker.chunk(body)
    joined = "".join(c.text for c in chunks)
    assert "/* comment ; still comment */" in joined


@pytest.mark.unit
def test_section_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunker, "_count_tokens", _wc_tokens)
    body = (
        "CREATE PROCEDURE X AS\nDECLARE\n  v INT;\nBEGIN\n  v := 1;\nEXCEPTION\n  v := 2;\nEND;\n"
    )
    chunks = chunker.chunk(body)
    hints = {c.section_hint for c in chunks}
    assert "declare" in hints
    assert "body" in hints
    assert "exception" in hints


@pytest.mark.unit
def test_reconstructs_most_of_the_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunker, "_count_tokens", _wc_tokens)
    body = "BEGIN\n" + " ".join(f"w{i}" for i in range(1000)) + ";\nEND;\n"
    chunks = chunker.chunk(body)
    reconstructed = _reconstruct_by_string_overlap(chunks)
    assert reconstructed == body


@pytest.mark.unit
@pytest.mark.adversarial
def test_adversarial_strings_and_comments_do_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunker, "_count_tokens", _wc_tokens)
    body = (
        "BEGIN\n"
        "  /* nested /* comment ; */ still comment */\n"
        "  x := 'END LOOP; not a real end';\n"
        "  y := (1 + (2 + 3));\n"
        "END;\n"
    )
    chunks = chunker.chunk(body)
    assert chunks
    reconstructed = _reconstruct_by_string_overlap(chunks)
    assert reconstructed == body


@pytest.mark.unit
@given(st.text(min_size=0, max_size=2000))
@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_does_not_drop_more_than_one_percent(body: str) -> None:
    original = chunker._count_tokens
    chunker._count_tokens = _wc_tokens
    try:
        chunks = chunker.chunk(body)
        reconstructed = _reconstruct_by_string_overlap(chunks)
    finally:
        chunker._count_tokens = original

    if not body.strip():
        assert reconstructed == ""
        return
    loss = abs(len(body) - len(reconstructed)) / max(1, len(body))
    assert not math.isnan(loss)
    assert loss <= 0.01
