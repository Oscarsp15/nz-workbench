"""Integration smoke test — requires a live nz-mcp + Netezza profile.

Enabled with ``NZ_WORKBENCH_RUN_INTEGRATION=1``.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.environ.get("NZ_WORKBENCH_RUN_INTEGRATION") != "1",
    reason="Set NZ_WORKBENCH_RUN_INTEGRATION=1 and configure nz-mcp with a live profile.",
)
def test_nz_mcp_client_initializes() -> None:
    """Verify that the MCP client can start nz-mcp and perform initialize."""
    from nz_workbench.nz_mcp_client.client import NzMcpClient

    client = NzMcpClient()
    try:
        client.start()
    finally:
        client.stop()
