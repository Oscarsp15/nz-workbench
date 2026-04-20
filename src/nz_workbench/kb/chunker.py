"""NZPLSQL body chunking for indexing.

Splits a procedure body into ~400-token chunks with 50-token overlap, respecting
``DECLARE`` / ``BEGIN`` / ``END LOOP`` boundaries and never breaking inside a string
literal, block comments, or parentheses of a single statement.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Final, cast

TARGET_TOKENS: Final[int] = 400
OVERLAP_TOKENS: Final[int] = 50
# Hard ceiling per chunk. BGE-M3 truncates above 8192 tokens silently, which
# means any logic past that cut never makes it into the embedding — zero recall
# on queries matching that zone. We pick 2000 to leave headroom while keeping
# blocks large enough to preserve semantic context.
MAX_TOKENS: Final[int] = 2000

# Bumped whenever the chunker output can change for the same input. Stored per
# procedure in the metadata DB; the indexer re-chunks+re-embeds when it drifts.
CHUNKER_VERSION: Final[int] = 1

_DEFAULT_TOKENIZER_MODEL: Final[str] = "BAAI/bge-m3"
_ENV_TOKENIZER_MODEL: Final[str] = "NZ_WORKBENCH_TOKENIZER_MODEL"

_AUTO_TOKENIZER: Any | None = None
_ImportedAutoTokenizer: Any
try:
    from transformers import AutoTokenizer as _ImportedAutoTokenizer
except Exception:  # pragma: no cover
    _ImportedAutoTokenizer = None
else:
    _AUTO_TOKENIZER = _ImportedAutoTokenizer


@dataclass(frozen=True, slots=True)
class Chunk:
    """One chunk of an NZPLSQL body, ready to embed."""

    text: str
    line_from: int
    line_to: int
    section_hint: str  # "header" | "declare" | "body" | "exception"


@dataclass(slots=True)
class _ScanState:
    in_string: bool = False
    block_comment_depth: int = 0
    paren_depth: int = 0


@dataclass(frozen=True, slots=True)
class _Segment:
    text: str
    line_from: int
    line_to: int
    section_hint: str
    token_count: int


@lru_cache(maxsize=1)
def _get_tokenizer() -> object:
    model_name = os.environ.get(_ENV_TOKENIZER_MODEL, _DEFAULT_TOKENIZER_MODEL)
    if _AUTO_TOKENIZER is None:  # pragma: no cover
        raise RuntimeError(
            "transformers is required for tokenizer-based chunk sizing; "
            "install nz-workbench with its dependencies."
        )

    auto_tok = cast(Any, _AUTO_TOKENIZER)
    return auto_tok.from_pretrained(model_name)


def _count_tokens(text: str) -> int:
    tok = _get_tokenizer()
    encoded = tok.encode(text, add_special_tokens=False)  # type: ignore[attr-defined]
    return len(encoded)


_RE_DECLARE: Final[re.Pattern[str]] = re.compile(r"^\s*DECLARE\b", re.IGNORECASE)
_RE_BEGIN: Final[re.Pattern[str]] = re.compile(r"^\s*BEGIN\b", re.IGNORECASE)
_RE_EXCEPTION: Final[re.Pattern[str]] = re.compile(r"^\s*EXCEPTION\b", re.IGNORECASE)
_RE_END_MARKERS: Final[re.Pattern[str]] = re.compile(
    r"\bEND\s+(LOOP|IF|CASE)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _LineScanner:
    line: str
    state: _ScanState
    i: int = 0
    in_line_comment: bool = False
    buf: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.buf = []

    def pieces(self) -> Iterable[tuple[str, bool]]:
        while self.i < len(self.line):
            if self.in_line_comment:
                yield from self._consume_line_comment()
                continue
            if self.state.in_string:
                self._consume_in_string()
                continue
            if self.state.block_comment_depth > 0:
                self._consume_in_block_comment()
                continue
            yield from self._consume_default()

        if self.buf:
            yield "".join(self.buf), False

    def _peek(self) -> str:
        if self.i + 1 >= len(self.line):
            return ""
        return self.line[self.i + 1]

    def _consume_line_comment(self) -> Iterable[tuple[str, bool]]:
        self.buf.append(self.line[self.i :])
        self.i = len(self.line)
        if self.buf:
            yield "".join(self.buf), False
            self.buf.clear()

    def _consume_in_string(self) -> None:
        ch = self.line[self.i]
        nxt = self._peek()
        self.buf.append(ch)
        if ch == "'" and nxt == "'":
            self.buf.append(nxt)
            self.i += 2
            return
        if ch == "'":
            self.state.in_string = False
        self.i += 1

    def _consume_in_block_comment(self) -> None:
        ch = self.line[self.i]
        nxt = self._peek()
        self.buf.append(ch)
        if ch == "/" and nxt == "*":
            self.buf.append(nxt)
            self.state.block_comment_depth += 1
            self.i += 2
            return
        if ch == "*" and nxt == "/":
            self.buf.append(nxt)
            self.state.block_comment_depth -= 1
            self.i += 2
            return
        self.i += 1

    def _consume_default(self) -> Iterable[tuple[str, bool]]:
        ch = self.line[self.i]
        nxt = self._peek()
        out: list[tuple[str, bool]] = []

        # Comment starts.
        if ch == "-" and nxt == "-":
            self.buf.append(ch)
            self.buf.append(nxt)
            self.in_line_comment = True
            self.i += 2
        elif ch == "/" and nxt == "*":
            self.buf.append(ch)
            self.buf.append(nxt)
            self.state.block_comment_depth += 1
            self.i += 2
        # String.
        elif ch == "'":
            self.buf.append(ch)
            self.state.in_string = True
            self.i += 1
        # Parentheses.
        elif ch == "(":
            self.buf.append(ch)
            self.state.paren_depth += 1
            self.i += 1
        elif ch == ")":
            self.buf.append(ch)
            if self.state.paren_depth > 0:
                self.state.paren_depth -= 1
            self.i += 1
        else:
            # Regular char (+ possible semicolon boundary).
            self.buf.append(ch)
            self.i += 1
            if ch == ";" and self.state.paren_depth == 0:
                piece = "".join(self.buf)
                self.buf.clear()
                out.append((piece, True))

        return out


def _iter_pieces_split_on_semicolons(line: str, state: _ScanState) -> Iterable[tuple[str, bool]]:
    """Yield (piece, boundary_after_piece) for top-level semicolons."""

    return _LineScanner(line=line, state=state).pieces()


def _segment(body: str) -> list[_Segment]:
    if not body.strip():
        return []

    lines = body.splitlines(keepends=True)
    state = _ScanState()
    segments: list[_Segment] = []
    buf: list[str] = []
    seg_line_from = 1
    current_section = "header"

    def flush_segment(line_to: int) -> None:
        nonlocal buf, seg_line_from
        text = "".join(buf)
        buf = []
        if not text:
            seg_line_from = line_to + 1
            return
        segments.append(
            _Segment(
                text=text,
                line_from=seg_line_from,
                line_to=line_to,
                section_hint=current_section,
                token_count=_count_tokens(text),
            )
        )
        seg_line_from = line_to + 1

    def maybe_switch_section(line: str, line_no: int) -> None:
        nonlocal current_section
        if state.block_comment_depth != 0 or state.in_string or state.paren_depth != 0:
            return
        if _RE_DECLARE.match(line):
            if buf:
                flush_segment(line_no - 1)
            current_section = "declare"
            return
        if _RE_BEGIN.match(line):
            if buf:
                flush_segment(line_no - 1)
            current_section = "body"
            return
        if _RE_EXCEPTION.match(line):
            if buf:
                flush_segment(line_no - 1)
            current_section = "exception"

    for idx0, line in enumerate(lines):
        line_no = idx0 + 1
        maybe_switch_section(line, line_no)

        for piece, boundary_after in _iter_pieces_split_on_semicolons(line, state):
            buf.append(piece)
            if boundary_after:
                flush_segment(line_no)

        if _RE_END_MARKERS.search(line):
            flush_segment(line_no)

    if buf:
        flush_segment(len(lines))

    return segments


def _safe_breakpoints(text: str) -> list[int]:
    """Return character indices where it's safe to split within a statement.

    A safe breakpoint is any whitespace position at top-level (not in strings,
    block/line comments, and with parentheses depth == 0).
    """
    return _BreakpointScanner(text=text).scan()


@dataclass(slots=True)
class _BreakpointScanner:
    text: str
    i: int = 0
    in_line_comment: bool = False
    state: _ScanState = None  # type: ignore[assignment]
    points: list[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.state = _ScanState()
        self.points = []

    def _peek(self) -> str:
        if self.i + 1 >= len(self.text):
            return ""
        return self.text[self.i + 1]

    def scan(self) -> list[int]:
        while self.i < len(self.text):
            if self.in_line_comment:
                self._consume_line_comment()
                continue
            if self.state.in_string:
                self._consume_in_string()
                continue
            if self.state.block_comment_depth > 0:
                self._consume_in_block_comment()
                continue
            self._consume_default()
        return self.points

    def _consume_line_comment(self) -> None:
        if self.text[self.i] == "\n":
            self.in_line_comment = False
        self.i += 1

    def _consume_in_string(self) -> None:
        ch = self.text[self.i]
        nxt = self._peek()
        if ch == "'" and nxt == "'":
            self.i += 2
            return
        if ch == "'":
            self.state.in_string = False
        self.i += 1

    def _consume_in_block_comment(self) -> None:
        ch = self.text[self.i]
        nxt = self._peek()
        if ch == "/" and nxt == "*":
            self.state.block_comment_depth += 1
            self.i += 2
            return
        if ch == "*" and nxt == "/":
            self.state.block_comment_depth -= 1
            self.i += 2
            return
        self.i += 1

    def _consume_default(self) -> None:
        ch = self.text[self.i]
        nxt = self._peek()

        if ch == "-" and nxt == "-":
            self.in_line_comment = True
            self.i += 2
            return
        if ch == "/" and nxt == "*":
            self.state.block_comment_depth += 1
            self.i += 2
            return
        if ch == "'":
            self.state.in_string = True
            self.i += 1
            return
        if ch == "(":
            self.state.paren_depth += 1
            self.i += 1
            return
        if ch == ")":
            if self.state.paren_depth > 0:
                self.state.paren_depth -= 1
            self.i += 1
            return

        if self.state.paren_depth == 0 and ch.isspace():
            self.points.append(self.i + 1)
        self.i += 1


def _split_oversized_segments(segments: list[_Segment], max_tokens: int) -> list[_Segment]:
    """Split any single segment that exceeds max_tokens at safe whitespace."""

    out: list[_Segment] = []
    for seg in segments:
        if seg.token_count <= max_tokens:
            out.append(seg)
            continue

        text = seg.text
        points = _safe_breakpoints(text)
        if not points:
            out.append(seg)
            continue

        remaining = text
        while _count_tokens(remaining) > max_tokens and points:
            total_tokens = _count_tokens(remaining)
            target_idx = int(len(remaining) * (max_tokens / max(1, total_tokens)))
            cut = max((p for p in points if p <= target_idx), default=points[0])
            # Ensure the cut actually respects max_tokens (token counting isn't linear in chars).
            while cut > 0 and _count_tokens(remaining[:cut]) > max_tokens:
                earlier = [p for p in points if p < cut]
                if not earlier:
                    break
                cut = max(earlier)
            if cut <= 0:
                break
            left, right = remaining[:cut], remaining[cut:]
            out.append(
                _Segment(
                    text=left,
                    line_from=seg.line_from,
                    line_to=seg.line_to,
                    section_hint=seg.section_hint,
                    token_count=_count_tokens(left),
                )
            )
            remaining = right
            points = [p - cut for p in points if p > cut]

        if remaining:
            out.append(
                _Segment(
                    text=remaining,
                    line_from=seg.line_from,
                    line_to=seg.line_to,
                    section_hint=seg.section_hint,
                    token_count=_count_tokens(remaining),
                )
            )

    return out


def _stitch(segments: list[_Segment], target_tokens: int, overlap_tokens: int) -> list[Chunk]:
    if not segments:
        return []

    chunks: list[Chunk] = []
    hard_max = target_tokens + 50
    start = 0
    while start < len(segments):
        end = start
        total = 0

        while end < len(segments):
            seg_tokens = segments[end].token_count
            if end == start:
                total += seg_tokens
                end += 1
                continue
            if (
                segments[end].section_hint in {"declare", "body", "exception"}
                and segments[end].section_hint != segments[start].section_hint
            ):
                break
            if total + seg_tokens > hard_max:
                break
            if total + seg_tokens > target_tokens and total >= target_tokens:
                break
            total += seg_tokens
            end += 1
            if total >= target_tokens:
                break

        chosen = segments[start:end]
        chunks.append(
            Chunk(
                text="".join(s.text for s in chosen),
                line_from=chosen[0].line_from,
                line_to=chosen[-1].line_to,
                section_hint=chosen[0].section_hint,
            )
        )

        if end >= len(segments):
            break

        new_start = end
        overlap = 0
        while new_start > start and overlap < overlap_tokens:
            new_start -= 1
            overlap += segments[new_start].token_count
        start = end if new_start == start else new_start

    return chunks


def _hard_split_text(text: str, max_tokens: int) -> list[str]:
    """Split text into pieces each tokenizing to ≤ ``max_tokens``.

    Prefers whitespace cuts near the estimated token-ratio target; falls back
    to character slicing if whitespace boundaries don't converge. Guarantees
    termination and progress: every iteration consumes ≥ 1 character.
    """

    if _count_tokens(text) <= max_tokens:
        return [text]

    pieces: list[str] = []
    remaining = text

    while _count_tokens(remaining) > max_tokens:
        total_tokens = _count_tokens(remaining)
        ratio = len(remaining) / max(1, total_tokens)
        # Target char index leaving a 10% safety margin below max_tokens.
        cut = max(1, int(max_tokens * ratio * 0.9))
        cut = min(cut, len(remaining) - 1)

        # Prefer a whitespace boundary within the second half of the estimate
        # so we don't shrink chunks dramatically hunting for whitespace.
        back = cut
        min_back = max(1, cut // 2)
        while back > min_back and not remaining[back].isspace():
            back -= 1
        if remaining[back : back + 1].isspace():
            cut = back

        # Guarantee the left half is under the ceiling; shrink if tokenization
        # came out above estimate.
        while cut > 1 and _count_tokens(remaining[:cut]) > max_tokens:
            cut = max(1, int(cut * 0.9))

        if cut <= 0:
            break

        pieces.append(remaining[:cut])
        remaining = remaining[cut:]

    if remaining:
        pieces.append(remaining)
    return pieces


def _enforce_chunk_ceiling(chunks: list[Chunk], max_tokens: int) -> list[Chunk]:
    """Post-processing guard: split any chunk whose text exceeds ``max_tokens``.

    The upstream logical/semicolon-aware splitter can leave oversized chunks
    when a single statement has no top-level whitespace breakpoints (rare but
    real). This safety net guarantees the invariant without requiring the
    upstream logic to be perfect.
    """

    out: list[Chunk] = []
    for ch in chunks:
        if _count_tokens(ch.text) <= max_tokens:
            out.append(ch)
            continue
        for piece in _hard_split_text(ch.text, max_tokens):
            out.append(
                Chunk(
                    text=piece,
                    line_from=ch.line_from,
                    line_to=ch.line_to,
                    section_hint=ch.section_hint,
                )
            )
    return out


def chunk(body: str) -> list[Chunk]:
    """Return the chunks of a procedure body."""

    segments = _segment(body)
    # ``_split_oversized_segments`` caps each segment near ``OVERLAP_TOKENS`` so
    # the stitch step's overlap loop can back up cleanly in small units; the
    # hard guarantee against BGE-M3 truncation comes from ``_enforce_chunk_ceiling``.
    segments = _split_oversized_segments(segments, max_tokens=OVERLAP_TOKENS)
    chunks = _stitch(segments, TARGET_TOKENS, OVERLAP_TOKENS)
    return _enforce_chunk_ceiling(chunks, MAX_TOKENS)


__all__ = [
    "CHUNKER_VERSION",
    "MAX_TOKENS",
    "OVERLAP_TOKENS",
    "TARGET_TOKENS",
    "Chunk",
    "chunk",
]
