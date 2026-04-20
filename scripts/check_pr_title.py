#!/usr/bin/env python
"""Validate PR title against the conventional-commits regex."""

from __future__ import annotations

import os
import re
import sys

TITLE_REGEX = re.compile(
    r"^(feat|fix|chore|refactor|docs|test|security|perf|build|ci|ren)"
    r"(\([a-z0-9-]+\))?(!)?: [^\s].{0,71}$"
)


def main() -> int:
    title = os.environ.get("PR_TITLE", "").strip()
    if not title:
        print("FAIL: empty PR title.", file=sys.stderr)
        return 1
    if not TITLE_REGEX.match(title):
        print(
            f"FAIL: PR title {title!r} no cumple el regex.\n"
            f"  Formato: <tipo>(<scope>)<!>: <descripción>\n"
            f"  Ejemplo: feat(kb): bootstrap indexa 6300 procedures",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
