"""MCP client to nz-mcp — the only path through which nz-workbench reaches Netezza."""

from __future__ import annotations

from nz_workbench.nz_mcp_client.client import NzMcpClient, ToolResult

__all__ = ["NzMcpClient", "ToolResult"]
