"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_kb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide a pristine `.nz-workbench/` directory per test and point config at it."""
    kb = tmp_path / "nz-workbench-state"
    kb.mkdir()
    monkeypatch.setenv("NZ_WORKBENCH_STATE_DIR", str(kb))
    return kb


@pytest.fixture
def tmp_profiles(tmp_path: Path) -> Path:
    """Provide a minimal `profiles.toml` with one admin profile for integration tests."""
    path = tmp_path / "profiles.toml"
    path.write_text(
        'active = "test-admin"\n'
        "[profiles.test-admin]\n"
        'host = "localhost"\n'
        "port = 5480\n"
        'database = "TESTDB"\n'
        'user = "tester"\n'
        'mode = "admin"\n',
        encoding="utf-8",
    )
    return path
