#!/usr/bin/env python
"""Validate that the branch name matches the project regex.

Reads the branch name from ``BRANCH`` env var (set by the workflow).
"""

from __future__ import annotations

import os
import re
import sys

BRANCH_REGEX = re.compile(
    r"^(feat|fix|chore|refactor|docs|test|security|perf|build|ci|ren)/\d+-[a-z0-9-]+$"
)


def main() -> int:
    branch = os.environ.get("BRANCH", "").strip()
    if not branch:
        print("FAIL: empty branch name (check BRANCH env var).", file=sys.stderr)
        return 1
    if not BRANCH_REGEX.match(branch):
        print(
            f"FAIL: branch {branch!r} no cumple el regex.\n"
            f"  Formato: <tipo>/<issue-o-ren>-<kebab-case>\n"
            f"  Tipos: feat|fix|chore|refactor|docs|test|security|perf|build|ci|ren\n"
            f"  Ejemplo: feat/12-kb-bootstrap",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
