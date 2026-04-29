from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from nz_workbench.cli import app


@pytest.mark.unit
def test_stub_commands_exit_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = CliRunner()
    monkeypatch.setattr("nz_workbench.cli.configure_logging_for_stdio", lambda: None)

    out = tmp_path / "kb.tar.zst"
    res_export = runner.invoke(app, ["kb-export", str(out)])
    assert res_export.exit_code == 0

    res_import = runner.invoke(app, ["kb-import", str(out)])
    assert res_import.exit_code == 0

    ren_folder = tmp_path / "REN_1"
    ren_folder.mkdir()
    res_analyze = runner.invoke(app, ["analyze", str(ren_folder)])
    assert res_analyze.exit_code == 0

    res_migrate = runner.invoke(app, ["migrate", str(ren_folder), "--dry-run"])
    assert res_migrate.exit_code == 0

    res_test = runner.invoke(app, ["test", str(ren_folder), "--phase", "baseline"])
    assert res_test.exit_code == 0

    res_doc = runner.invoke(app, ["doc-update", str(ren_folder)])
    assert res_doc.exit_code == 0

    res_explain = runner.invoke(app, ["explain", "PROD_X.DBO.SP1"])
    assert res_explain.exit_code == 0

    res_search = runner.invoke(app, ["search", "saldo cascada", "--k", "3"])
    assert res_search.exit_code == 0


@pytest.mark.unit
def test_serve_command_runs_mcp_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that serve command calls run_stdio_server."""
    runner = CliRunner()
    monkeypatch.setattr("nz_workbench.cli.configure_logging_for_stdio", lambda: None)

    # Mock the MCP server runner to avoid actual stdio operations
    server_called = False

    def mock_run_stdio_server() -> None:
        nonlocal server_called
        server_called = True

    monkeypatch.setattr("nz_workbench.cli.run_stdio_server", mock_run_stdio_server)

    res = runner.invoke(app, ["serve"])
    assert res.exit_code == 0
    assert server_called
