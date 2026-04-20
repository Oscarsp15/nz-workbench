"""Logging configuration for stdio (CLI + MCP server).

Routes both stdlib logging and structlog to stderr, and silences noisy third-party
loggers (Chroma, sentence-transformers, torch).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any, Final

import structlog

_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "chromadb",
    "sentence_transformers",
    "transformers",
    "torch",
    "urllib3",
)


class _SuppressState:
    """Mutable switch read by the structlog processor on every call.

    Toggled by long-running CLI UI (e.g. the kb-bootstrap Rich progress bar)
    to drop INFO/DEBUG structlog events that would shred the in-place render.
    A processor-based filter works regardless of logger caching, unlike
    ``structlog.configure(wrapper_class=...)`` which only affects loggers
    created *after* the reconfigure.
    """

    suppress: bool = False


def set_suppress_info_events(active: bool) -> None:
    """Toggle INFO/DEBUG silencing for structlog output."""

    _SuppressState.suppress = active


def _drop_info_when_suppressed(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    if _SuppressState.suppress and event_dict.get("level") in {"debug", "info"}:
        raise structlog.DropEvent
    return event_dict


def configure_logging_for_stdio(level: int = logging.INFO) -> None:
    """Configure logging so that stderr remains readable under stdio transports."""

    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(message)s",
    )

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            _drop_info_when_suppressed,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.KeyValueRenderer(
                key_order=["event", "level", "timestamp"],
                sort_keys=True,
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


__all__ = ["configure_logging_for_stdio", "set_suppress_info_events"]
