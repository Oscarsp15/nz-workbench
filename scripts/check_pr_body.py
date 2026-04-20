#!/usr/bin/env python
"""Validate that the PR body contains the mandatory template headings.

Source of truth: ``.github/PULL_REQUEST_TEMPLATE.md`` and
``docs/standards/pr-audit.md``.
"""

from __future__ import annotations

import os
import sys
from typing import Final

REQUIRED_HEADINGS: Final[tuple[str, ...]] = (
    "## ¿Qué cambia?",
    "## Issue relacionado",
    "## Acción según AGENTS.md",
    "## Auditoría pre-merge",
    "## Validación humana",
)


def missing_headings(body: str, *, required: tuple[str, ...] = REQUIRED_HEADINGS) -> list[str]:
    return [h for h in required if h not in body]


def main() -> int:
    body = os.environ.get("PR_BODY", "") or ""
    missing = missing_headings(body)
    if missing:
        lines = [
            "FAIL: el cuerpo del PR no cumple la estructura mínima del template.",
            "",
            "Encabezados obligatorios faltantes:",
        ]
        lines.extend(f"  - {h}" for h in missing)
        lines.extend(
            [
                "",
                "Usá la plantilla en .github/PULL_REQUEST_TEMPLATE.md.",
                "Podés editar el body del PR sin re-commit:",
                "  gh pr edit <N> --body-file /ruta/a/body.md",
            ]
        )
        print("\n".join(lines), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
