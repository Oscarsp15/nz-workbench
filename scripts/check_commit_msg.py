#!/usr/bin/env python
"""Validate a commit message subject against the project regex.

Used as a local ``commit-msg`` pre-commit hook. Receives the path to the commit
message file as ``argv[1]``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SUBJECT_REGEX = re.compile(
    r"^(feat|fix|chore|refactor|docs|test|security|perf|build|ci|ren)"
    r"(\([a-z0-9-]+\))?(!)?: [^\s].{0,71}$"
)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("FAIL: missing commit message path.", file=sys.stderr)
        return 1
    msg_path = Path(argv[1])
    if not msg_path.exists():
        print(f"FAIL: does not exist {msg_path}.", file=sys.stderr)
        return 1
    raw = msg_path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    if not lines:
        print("FAIL: empty commit message.", file=sys.stderr)
        return 1
    subject = lines[0].rstrip()
    if subject.startswith(("Merge ", "Revert ", "fixup!", "squash!")):
        return 0
    if not SUBJECT_REGEX.match(subject):
        print(
            f"FAIL: commit subject does not match the regex.\n"
            f"  Received: {subject!r}\n"
            f"  Format:   <type>(<scope>)<!>: <description>\n"
            f"  Types:    feat|fix|chore|refactor|docs|test|security|perf|build|ci|ren\n"
            f"  Rules:    72 chars max, imperative, lowercase first letter, no trailing period.\n"
            f"  Example:  feat(kb): bootstrap indexa 6300 procedures",
            file=sys.stderr,
        )
        return 1
    if len(lines) >= 2 and lines[1].strip():
        print(
            "FAIL: a commit with a body must have an empty line between subject and body.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
