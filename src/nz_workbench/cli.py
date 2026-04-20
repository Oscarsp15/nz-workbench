"""Typer CLI for nz-workbench."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from nz_workbench import __version__
from nz_workbench.kb import indexer as kb_indexer
from nz_workbench.logging_config import configure_logging_for_stdio
from nz_workbench.mcp_server import run_stdio_server

app = typer.Typer(
    name="nz-workbench",
    help="AI-assisted workbench for IBM Netezza procedure maintenance.",
    no_args_is_help=True,
    add_completion=False,
)

_ARG_PROC_FQN = typer.Argument(..., help="Fully qualified procedure name (DB.SCHEMA.NAME).")
_ARG_KB_EXPORT_OUT = typer.Argument(..., help="Output archive path (e.g. kb.tar.zst).")
_ARG_KB_IMPORT_ARCHIVE = typer.Argument(..., help="Archive to import (from kb-export).")
_ARG_REN_FOLDER_SOURCE = typer.Argument(..., help="Path to ren/REN_<N>/ with source.md inside.")
_ARG_REN_FOLDER_MANIFEST = typer.Argument(..., help="Path to ren/REN_<N>/ with manifest.yaml.")
_ARG_REN_FOLDER_ANY = typer.Argument(..., help="Path to ren/REN_<N>/ .")
_ARG_REN_FOLDER_APPROVED = typer.Argument(..., help="Path to ren/REN_<N>/ after approval.")


def _parse_csv(value: str) -> list[str]:
    items = [x.strip() for x in value.split(",")]
    return [x for x in items if x]


@contextmanager
def _progress_context() -> Iterator[kb_indexer.ProgressCallback]:
    """Render a Rich progress bar on stderr and yield a callback that drives it.

    Raises the root-logger level to WARNING while active so INFO events from
    the indexer don't shred the bar. The bar is transient and clears on exit
    so the final report table prints cleanly.
    """

    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.WARNING)

    console = Console(stderr=True)
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        console=console,
        transient=True,
        refresh_per_second=4,
    )

    try:
        progress.start()
        task_id = progress.add_task("Discovering procedures...", total=None)

        def _on_progress(event: kb_indexer.ProgressEvent) -> None:
            stage = event.get("stage")
            if stage == "total_update":
                total = event.get("total")
                if isinstance(total, int):
                    progress.update(task_id, total=total)
            elif stage == "proc_start":
                desc = f"{event['database']}.{event['schema']}.{event['name']}"
                progress.update(task_id, description=desc)
            elif stage == "proc_done":
                progress.update(task_id, advance=1)

        yield _on_progress
    finally:
        progress.stop()
        root_logger.setLevel(previous_level)


def _print_index_report(title: str, report: kb_indexer.IndexReport) -> None:
    console = Console()
    emit = console.print
    table = Table(title=title)
    table.add_column("Procedures indexed", justify="right")
    table.add_column("Procedures skipped", justify="right")
    table.add_column("Chunks written", justify="right")
    table.add_column("Duration (s)", justify="right")
    table.add_row(
        str(report.procedures_indexed),
        str(report.procedures_skipped),
        str(report.chunks_written),
        f"{report.duration_seconds:.2f}",
    )
    emit(table)

    if report.errors:
        emit("\nErrors:")
        for err in report.errors:
            emit(f"- {err}")


@app.command("version")
def version_cmd() -> None:
    """Print the installed nz-workbench version."""

    typer.echo(__version__)


@app.command("kb-bootstrap")
def kb_bootstrap_cmd(
    databases: str = typer.Option(
        ...,
        "--databases",
        "-d",
        help="Comma-separated list of PROD databases to index.",
    ),
    top_n: int | None = typer.Option(
        None,
        "--top",
        help="Optional: index only top-N procedures (by size) per database.",
    ),
) -> None:
    """Index production procedures into the local knowledge base (one-time)."""

    configure_logging_for_stdio()
    dbs = _parse_csv(databases)
    if not dbs:
        raise typer.BadParameter("at least one database is required")

    with _progress_context() as on_progress:
        report = kb_indexer.bootstrap(dbs, top_n=top_n, on_progress=on_progress)
    _print_index_report("KB bootstrap", report)
    raise typer.Exit(code=1 if report.errors else 0)


@app.command("kb-refresh")
def kb_refresh_cmd(
    target: str = _ARG_PROC_FQN,
) -> None:
    """Re-index a single procedure when you know it changed in PROD."""

    configure_logging_for_stdio()
    parts = [p.strip() for p in target.split(".") if p.strip()]
    fqn_parts = 3
    if len(parts) != fqn_parts:
        raise typer.BadParameter("expected DB.SCHEMA.NAME")
    db, schema, name = parts
    with _progress_context() as on_progress:
        report = kb_indexer.refresh_one(db, schema, name, on_progress=on_progress)
    _print_index_report("KB refresh", report)
    raise typer.Exit(code=1 if report.errors else 0)


@app.command("kb-refresh-cron")
def kb_refresh_cron_cmd() -> None:
    """Scan _V_PROCEDURE.LASTALTERTIME and re-index changed procedures (opt-in cron)."""

    configure_logging_for_stdio()
    with _progress_context() as on_progress:
        report = kb_indexer.refresh_cron(on_progress=on_progress)
    _print_index_report("KB refresh-cron", report)
    raise typer.Exit(code=1 if report.errors else 0)


@app.command("kb-export")
def kb_export_cmd(
    out: Path = _ARG_KB_EXPORT_OUT,
) -> None:
    """Export the local KB as a portable archive."""

    typer.echo(f"[stub] kb-export → {out}")
    raise typer.Exit(code=0)


@app.command("kb-import")
def kb_import_cmd(
    archive: Path = _ARG_KB_IMPORT_ARCHIVE,
) -> None:
    """Import a KB archive into this machine's .nz-workbench/ directory."""

    typer.echo(f"[stub] kb-import ← {archive}")
    raise typer.Exit(code=0)


@app.command("analyze")
def analyze_cmd(
    ren_folder: Path = _ARG_REN_FOLDER_SOURCE,
) -> None:
    """Analyze a REN and produce analysis.yaml + clarifications.md."""

    typer.echo(f"[stub] analyze {ren_folder}")
    raise typer.Exit(code=0)


@app.command("migrate")
def migrate_cmd(
    ren_folder: Path = _ARG_REN_FOLDER_MANIFEST,
    dry_run: bool = typer.Option(True, "--dry-run/--confirm", help="Dry-run or commit to DESA_*."),
) -> None:
    """Clone the procedures listed in the manifest into DESA_* with rewrite rules."""

    typer.echo(f"[stub] migrate {ren_folder} dry_run={dry_run}")
    raise typer.Exit(code=0)


@app.command("test")
def test_cmd(
    ren_folder: Path = _ARG_REN_FOLDER_ANY,
    phase: str = typer.Option("both", "--phase", help="baseline | comparison | both"),
) -> None:
    """Run baseline (phase 6) and/or comparison (phase 8) for the REN."""

    typer.echo(f"[stub] test {ren_folder} phase={phase}")
    raise typer.Exit(code=0)


@app.command("doc-update")
def doc_update_cmd(
    ren_folder: Path = _ARG_REN_FOLDER_APPROVED,
) -> None:
    """Append the REN's change log to each touched procedure's doc file."""

    typer.echo(f"[stub] doc-update {ren_folder}")
    raise typer.Exit(code=0)


@app.command("explain")
def explain_cmd(
    target: str = typer.Argument(..., help="Fully qualified procedure name (DB.SCHEMA.NAME)."),
) -> None:
    """Generate a pedagogical mapping of a procedure (uses Claude tokens)."""

    typer.echo(f"[stub] explain {target}")
    raise typer.Exit(code=0)


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Free-text search query."),
    k: int = typer.Option(10, "--k", help="Number of results to return."),
) -> None:
    """Hybrid semantic + structural search over the KB."""

    typer.echo(f"[stub] search {query!r} k={k}")
    raise typer.Exit(code=0)


@app.command("serve")
def serve_cmd() -> None:
    """Run the MCP server over stdio for Claude CLI / Desktop integration."""

    configure_logging_for_stdio()
    run_stdio_server()
