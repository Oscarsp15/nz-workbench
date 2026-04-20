from __future__ import annotations

import pytest
from typer.testing import CliRunner

from nz_workbench.cli import app
from nz_workbench.kb.indexer import IndexReport, ProgressCallback


@pytest.mark.unit
def test_kb_bootstrap_parses_databases_and_propagates_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()
    called: list[tuple[list[str], int | None]] = []

    def fake_bootstrap(
        databases: list[str],
        top_n: int | None = None,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> IndexReport:
        called.append((databases, top_n))
        if on_progress is not None:
            on_progress({"stage": "total_update", "total": 1})
            on_progress(
                {
                    "stage": "proc_start",
                    "database": "PROD_A",
                    "schema": "DBO",
                    "name": "SP1",
                }
            )
            on_progress(
                {
                    "stage": "proc_done",
                    "database": "PROD_A",
                    "schema": "DBO",
                    "name": "SP1",
                    "chunks": 2,
                    "indexed": True,
                    "skipped": False,
                    "error": None,
                }
            )
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

    def fake_bootstrap_err(
        databases: list[str],
        top_n: int | None = None,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> IndexReport:
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

    def _fake_refresh_one(
        db: str,
        schema: str,
        name: str,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> IndexReport:
        return IndexReport(0, 1, 0, 0.0, [])

    monkeypatch.setattr("nz_workbench.cli.kb_indexer.refresh_one", _fake_refresh_one)

    ok = runner.invoke(app, ["kb-refresh", "PROD_X.DBO.SP1"])
    assert ok.exit_code == 0

    bad = runner.invoke(app, ["kb-refresh", "SP1"])
    assert bad.exit_code != 0


@pytest.mark.unit
def test_kb_refresh_cron_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr("nz_workbench.cli.configure_logging_for_stdio", lambda: None)

    def _fake_refresh_cron(*, on_progress: ProgressCallback | None = None) -> IndexReport:
        return IndexReport(0, 0, 0, 0.0, ["err"])

    monkeypatch.setattr("nz_workbench.cli.kb_indexer.refresh_cron", _fake_refresh_cron)
    res = runner.invoke(app, ["kb-refresh-cron"])
    assert res.exit_code == 1
