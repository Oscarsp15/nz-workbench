#!/usr/bin/env python
"""Block common hygiene mistakes in PRs.

- No large binaries (> 1 MB) checked in.
- No files containing the "TODO-remove" marker used for temporary notes.
- No `print(` statements in src/ (structlog must be used instead).
- No `profiles.toml` or `*.env` accidentally committed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

_MAX_FILE_SIZE: Final[int] = 1_048_576  # 1 MB
_FORBIDDEN_FILES: Final[set[str]] = {"profiles.toml", ".env"}
_FORBIDDEN_PATTERNS: Final[tuple[str, ...]] = ("TODO: remove before " + "merge",)


def _staged_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(p) for p in result.stdout.splitlines() if p.strip()]


def main() -> int:
    problems: list[str] = []
    for path in _staged_files():
        if path.name in _FORBIDDEN_FILES:
            problems.append(f"forbidden file committed: {path}")
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > _MAX_FILE_SIZE:
            problems.append(f"file {path} too large ({size} bytes > {_MAX_FILE_SIZE})")
        if path.suffix in {".py", ".md", ".yaml", ".yml", ".toml"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in _FORBIDDEN_PATTERNS:
                if pattern in text:
                    problems.append(f"{path}: contains forbidden pattern {pattern!r}")
            if path.parts and path.parts[0] == "src" and "print(" in text:
                problems.append(f"{path}: uses print(). Use structlog instead.")
    if problems:
        print("FAIL: repo hygiene issues:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
