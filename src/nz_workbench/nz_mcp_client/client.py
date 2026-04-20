"""Client to the ``nz-mcp`` MCP server. Single instance per process, lazy start.

Why go through nz-mcp: see ADR 0004. Rationale summary — zero duplication of
connection logic, sql_guard, identifier validation, keyring, NZPLSQL parsing,
and automatic inheritance of security fixes merged into the public project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Structured result of an MCP tool call."""

    ok: bool
    result: dict[str, Any] | None
    error_code: str | None
    error_context: dict[str, Any] | None


class NzMcpClient:
    """Connects to ``nz-mcp serve`` as a subprocess via stdio JSON-RPC."""

    def __init__(self, bin_path: str = "nz-mcp") -> None:
        self._bin_path = bin_path

    def start(self) -> None:
        """Spawn the nz-mcp subprocess and perform MCP initialize."""
        raise NotImplementedError

    def stop(self) -> None:
        """Gracefully close the subprocess."""
        raise NotImplementedError

    def call(self, tool: str, arguments: dict[str, Any]) -> ToolResult:
        """Invoke a tool by name and return its structured result."""
        raise NotImplementedError


__all__ = ["NzMcpClient", "ToolResult"]
