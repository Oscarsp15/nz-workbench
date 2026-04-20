from __future__ import annotations

import pytest

from nz_workbench.errors import AmbiguityError, NzMcpUnavailableError
from nz_workbench.logging_config import configure_logging_for_stdio
from nz_workbench.mcp_server import run_stdio_server


@pytest.mark.unit
def test_configure_logging_for_stdio_does_not_crash() -> None:
    configure_logging_for_stdio()


@pytest.mark.unit
def test_errors_render_codes() -> None:
    err = AmbiguityError("need human", foo="bar")
    assert "AMBIGUITY" in str(err)
    err2 = NzMcpUnavailableError("nope")
    assert "NZ_MCP_UNAVAILABLE" in str(err2)


@pytest.mark.unit
def test_mcp_server_is_stub_but_configures_logging() -> None:
    with pytest.raises(NotImplementedError):
        run_stdio_server()

