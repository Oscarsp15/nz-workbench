"""MCP server entry for nz-workbench.

Exposes the workbench's own tools (REN analysis, migration, testing) over stdio so that
Claude CLI / Desktop can drive them. Internally uses ``nz-mcp`` as a subprocess to reach
Netezza.

This module is a skeleton — full wiring to the MCP SDK is added in subsequent iterations.
"""

from __future__ import annotations

from typing import Final


def run_stdio_server() -> None:
    """Run the MCP server over stdio.

    Placeholder: full implementation will mirror ``nz-mcp``'s server.py pattern —
    register every workbench tool, route stdio JSON-RPC, configure logging to stderr.
    """
    msg: Final[str] = (
        "nz-workbench MCP server — not yet implemented. "
        "This is the bootstrap scaffolding."
    )
    raise NotImplementedError(msg)


__all__ = ["run_stdio_server"]
