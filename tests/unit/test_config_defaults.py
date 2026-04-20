"""Basic config resolution test."""

from __future__ import annotations

from pathlib import Path

import pytest

from nz_workbench.config import load_config, project_root


@pytest.mark.unit
def test_config_defaults() -> None:
    cfg = load_config()
    assert cfg.nz_mcp_bin == "nz-mcp"
    assert cfg.embedder_model == "BAAI/bge-m3"
    assert cfg.chunk_tokens == 400
    assert cfg.chunk_overlap_tokens == 50


@pytest.mark.unit
def test_config_state_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NZ_WORKBENCH_STATE_DIR", str(tmp_path))
    cfg = load_config()
    assert cfg.state_dir == tmp_path


@pytest.mark.unit
def test_project_root_exists() -> None:
    root = project_root()
    assert root.exists()
    assert (root / "pyproject.toml").is_file()
