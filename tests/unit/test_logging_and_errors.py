from __future__ import annotations

import io
import logging

import pytest
import structlog

from nz_workbench.errors import AmbiguityError, NzMcpUnavailableError
from nz_workbench.logging_config import configure_logging_for_stdio, set_suppress_info_events
from nz_workbench.mcp_server import run_stdio_server


@pytest.mark.unit
def test_configure_logging_for_stdio_does_not_crash() -> None:
    configure_logging_for_stdio()


@pytest.mark.unit
def test_suppress_info_events_drops_structlog_info_while_active(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When suppression is on, ``log.info`` emits nothing; errors still flow."""

    configure_logging_for_stdio(level=logging.INFO)
    buffer = io.StringIO()
    log = structlog.wrap_logger(structlog.PrintLogger(file=buffer))

    set_suppress_info_events(True)
    try:
        log.info("noisy_event", payload="x")
        log.warning("still_visible")
    finally:
        set_suppress_info_events(False)

    # Capture stderr too, since PrintLogger defaults may target it elsewhere.
    captured = buffer.getvalue() + capsys.readouterr().err
    assert "noisy_event" not in captured, captured
    assert "still_visible" in captured, captured

    # After toggling off: INFO is visible again.
    buffer.seek(0)
    buffer.truncate()
    log.info("back_online")
    post = buffer.getvalue() + capsys.readouterr().err
    assert "back_online" in post, post


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
