"""Typed errors raised by nz-workbench modules."""

from __future__ import annotations

from typing import Any


class NzWorkbenchError(Exception):
    """Base for all workbench-specific errors."""

    code: str = "NZ_WORKBENCH_ERROR"

    def __init__(self, detail: str, **context: Any) -> None:
        self.detail = detail
        self.context = context
        super().__init__(f"[{self.code}] {detail}")


class AmbiguityError(NzWorkbenchError):
    """Raised when the AI would have to guess. The human must resolve."""

    code = "AMBIGUITY"


class ManifestError(NzWorkbenchError):
    """Manifest.yaml is malformed or inconsistent with the state of the repo."""

    code = "MANIFEST_ERROR"


class BaselineFailedError(NzWorkbenchError):
    """Baseline comparison diverged. No edits are applied."""

    code = "BASELINE_FAILED"


class NzMcpUnavailableError(NzWorkbenchError):
    """Cannot reach the ``nz-mcp`` subprocess."""

    code = "NZ_MCP_UNAVAILABLE"


__all__ = [
    "NzWorkbenchError",
    "AmbiguityError",
    "ManifestError",
    "BaselineFailedError",
    "NzMcpUnavailableError",
]
