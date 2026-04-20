"""MCP server entry for nz-workbench.

This module is still a skeleton: full wiring to the MCP SDK is added in subsequent
iterations. It already configures logging for stdio to keep stderr usable.
"""

from __future__ import annotations

from typing import Final

from nz_workbench.logging_config import configure_logging_for_stdio


def run_stdio_server() -> None:
    """Run the MCP server over stdio."""

    configure_logging_for_stdio()
    msg: Final[str] = (
        "nz-workbench MCP server — not yet implemented. This is the bootstrap scaffolding."
    )
    raise NotImplementedError(msg)


__all__ = ["run_stdio_server"]
