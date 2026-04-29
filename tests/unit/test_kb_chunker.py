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
    chunker._count_tokens = _wc_tokens  # type: ignore[assignment]
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


def test_chunk_enforces_max_tokens_on_monolithic_body() -> None:
    """A body with no logical boundaries must still be split ≤ MAX_TOKENS.

    Simulates a procedure with one gigantic statement and no semicolons at top
    level — the shape that caused the BGE-M3 truncation warning in production.
    """

    original = chunker._count_tokens
    chunker._count_tokens = _wc_tokens  # type: ignore[assignment]
    try:
        # 12000 whitespace-separated words, no semicolons, no BEGIN/END — the
        # chunker's logical splitter has nothing to latch onto, so the ceiling
        # is the only defense.
        body = " ".join(f"w{i}" for i in range(12000))
        chunks = chunker.chunk(body)

        assert chunks, "chunker must emit at least one chunk"
        for ch in chunks:
            assert _wc_tokens(ch.text) <= chunker.MAX_TOKENS, (
                f"chunk over MAX_TOKENS={chunker.MAX_TOKENS}: got {_wc_tokens(ch.text)}"
            )
    finally:
        chunker._count_tokens = original


def test_chunker_version_is_positive_int() -> None:
    """Sanity: CHUNKER_VERSION exists and starts at ≥ 1 (0 = pre-versioning)."""

    assert isinstance(chunker.CHUNKER_VERSION, int)
    assert chunker.CHUNKER_VERSION >= 1


@pytest.mark.unit
def test_large_sp_10k_lines_never_exceeds_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test for Issue #20: SPs with 10000+ lines must never produce
    a chunk exceeding MAX_TOKENS (BGE-M3 would truncate or raise a warning)."""

    monkeypatch.setattr(chunker, "_count_tokens", _wc_tokens)

    # Simulates a real large SP: header, DECLARE block, many assignments, END.
    lines = ["CREATE PROCEDURE PI_CONTINGENCIA_RIESGOS_MOTOR() RETURNS INT AS"]
    lines.append("DECLARE")
    for i in range(2000):
        lines.append(f"  v_var_{i} INT;")
    lines.append("BEGIN")
    for i in range(8000):
        lines.append(f"  v_var_{i % 2000} := {i};")
    lines.append("END;")
    body = "\n".join(lines)

    chunks = chunker.chunk(body)
    assert chunks, "chunker must produce at least one chunk for a large SP"
    for ch in chunks:
        tok_count = _wc_tokens(ch.text)
        assert tok_count <= chunker.MAX_TOKENS, (
            f"chunk exceeded MAX_TOKENS={chunker.MAX_TOKENS}: got {tok_count}. "
            "BGE-M3 would truncate this chunk silently."
        )


@pytest.mark.unit
def test_bge_max_tokens_constant_exists() -> None:
    """BGE_MAX_TOKENS must be exported and set to 8192 (BGE-M3 hard limit)."""

    assert hasattr(chunker, "BGE_MAX_TOKENS")
    assert chunker.BGE_MAX_TOKENS == 8192
    # MAX_TOKENS (our soft ceiling) must be safely below the hard limit.
    assert chunker.MAX_TOKENS < chunker.BGE_MAX_TOKENS


@pytest.mark.unit
def test_hard_split_text_guarantees_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every piece produced by _hard_split_text must respect max_tokens."""

    monkeypatch.setattr(chunker, "_count_tokens", _wc_tokens)
    # 5000 words with no whitespace-friendly breakpoints inside long tokens.
    text = " ".join(f"tok{i}" for i in range(5000))
    pieces = chunker._hard_split_text(text, max_tokens=200)

    assert pieces, "_hard_split_text must return at least one piece"
    for piece in pieces:
        assert _wc_tokens(piece) <= 200, (
            f"_hard_split_text returned a piece with {_wc_tokens(piece)} tokens "
            f"(max_tokens=200): {piece[:80]!r}..."
        )
