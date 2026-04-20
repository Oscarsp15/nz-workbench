"""Logging configuration for stdio (CLI + MCP server).

Routes both stdlib logging and structlog to stderr, and silences noisy third-party
loggers (Chroma, sentence-transformers, torch).
"""

from __future__ import annotations

import logging
import sys
from typing import Final

import structlog

_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "chromadb",
    "sentence_transformers",
    "transformers",
    "torch",
    "urllib3",
)


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


__all__ = ["configure_logging_for_stdio"]
