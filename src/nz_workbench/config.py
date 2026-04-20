"""Runtime configuration for nz-workbench.

Values can be overridden via environment variables prefixed ``NZ_WORKBENCH_*``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

# Project root resolved at import time (../../ from this file).
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

# Local state directory — never committed.
_DEFAULT_STATE_DIR: Final[Path] = _PROJECT_ROOT / ".nz-workbench"

# Environment variable names.
ENV_STATE_DIR: Final[str] = "NZ_WORKBENCH_STATE_DIR"
ENV_NZ_MCP_BIN: Final[str] = "NZ_MCP_BIN"
ENV_EMBEDDER_MODEL: Final[str] = "NZ_WORKBENCH_EMBEDDER"
ENV_RUN_INTEGRATION: Final[str] = "NZ_WORKBENCH_RUN_INTEGRATION"


class Config(BaseModel):
    """Resolved configuration used across modules."""

    model_config = ConfigDict(frozen=True)

    state_dir: Path = Field(default=_DEFAULT_STATE_DIR)
    nz_mcp_bin: str = Field(default="nz-mcp")
    embedder_model: str = Field(default="BAAI/bge-m3")
    chunk_tokens: int = Field(default=400, ge=100, le=2000)
    chunk_overlap_tokens: int = Field(default=50, ge=0, le=500)


def load_config() -> Config:
    """Return a ``Config`` with environment overrides applied."""
    return Config(
        state_dir=Path(os.environ.get(ENV_STATE_DIR, str(_DEFAULT_STATE_DIR))),
        nz_mcp_bin=os.environ.get(ENV_NZ_MCP_BIN, "nz-mcp"),
        embedder_model=os.environ.get(ENV_EMBEDDER_MODEL, "BAAI/bge-m3"),
    )


def project_root() -> Path:
    """Return the absolute path of the repository root."""
    return _PROJECT_ROOT


__all__ = [
    "Config",
    "load_config",
    "project_root",
    "ENV_EMBEDDER_MODEL",
    "ENV_NZ_MCP_BIN",
    "ENV_RUN_INTEGRATION",
    "ENV_STATE_DIR",
]
