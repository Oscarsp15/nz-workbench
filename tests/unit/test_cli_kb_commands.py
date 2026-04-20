from __future__ import annotations

import pytest
from typer.testing import CliRunner

from nz_workbench.cli import app
from nz_workbench.kb.indexer import IndexReport


@pytest.mark.unit
def test_kb_bootstrap_parses_databases_and_propagates_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    called: list[tuple[list[str], int | None]] = []

    def fake_bootstrap(databases: list[str], top_n: int | None = None) -> IndexReport:
        called.append((databases, top_n))
        return IndexReport(
            procedures_indexed=1,
            procedures_skipped=0,
            chunks_written=2,
            duration_seconds=0.1,
            errors=[],
        )

    monkeypatch.setattr("nz_workbench.cli.configure_logging_for_stdio", lambda: None)
    monkeypatch.setattr("nz_workbench.cli.kb_indexer.bootstrap", fake_bootstrap)

    res = runner.invoke(app, ["kb-bootstrap", "--databases", "PROD_A, PROD_B", "--top", "1"])
    assert res.exit_code == 0
    assert called == [(["PROD_A", "PROD_B"], 1)]

    def fake_bootstrap_err(databases: list[str], top_n: int | None = None) -> IndexReport:
        called.append((databases, top_n))
        return IndexReport(
            procedures_indexed=0,
            procedures_skipped=0,
            chunks_written=0,
            duration_seconds=0.1,
            errors=["boom"],
        )

    monkeypatch.setattr("nz_workbench.cli.kb_indexer.bootstrap", fake_bootstrap_err)
    res2 = runner.invoke(app, ["kb-bootstrap", "--databases", "PROD_A"])
    assert res2.exit_code == 1

    version = runner.invoke(app, ["version"])
    assert version.exit_code == 0
    assert version.stdout.strip()

    empty = runner.invoke(app, ["kb-bootstrap", "--databases", ""])
    assert empty.exit_code != 0


@pytest.mark.unit
def test_kb_refresh_validates_fqn(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr("nz_workbench.cli.configure_logging_for_stdio", lambda: None)
    monkeypatch.setattr(
        "nz_workbench.cli.kb_indexer.refresh_one",
        lambda db, schema, name: IndexReport(0, 1, 0, 0.0, []),
    )

    ok = runner.invoke(app, ["kb-refresh", "PROD_X.DBO.SP1"])
    assert ok.exit_code == 0

    bad = runner.invoke(app, ["kb-refresh", "SP1"])
    assert bad.exit_code != 0


@pytest.mark.unit
def test_kb_refresh_cron_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr("nz_workbench.cli.configure_logging_for_stdio", lambda: None)
    monkeypatch.setattr(
        "nz_workbench.cli.kb_indexer.refresh_cron",
        lambda: IndexReport(0, 0, 0, 0.0, ["err"]),
    )
    res = runner.invoke(app, ["kb-refresh-cron"])
    assert res.exit_code == 1
