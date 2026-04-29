"""Typer CLI for nz-workbench."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

import typer
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nz_workbench import __version__
from nz_workbench.kb import indexer as kb_indexer
from nz_workbench.kb.embedder import get_hardware_info
from nz_workbench.logging_config import configure_logging_for_stdio, set_suppress_info_events
from nz_workbench.mcp_server import run_stdio_server

_PROGRESS_BAR_WIDTH = 30

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


def _get_hardware_line() -> str:
    """Return hardware info as a formatted string."""
    hw = get_hardware_info()
    if hw.device == "cuda" and hw.gpu_name:
        vram_str = f", {hw.vram_gb}GB" if hw.vram_gb else ""
        return f"[green]CUDA[/green] ({hw.gpu_name}{vram_str}) │ Batch: {hw.batch_size}"
    return f"[yellow]CPU[/yellow] │ Batch: {hw.batch_size}"


def _format_bytes(b: int) -> str:
    """Format bytes as human-readable MB."""
    return f"{b / (1024 * 1024):.1f} MB"


def _format_time(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    if seconds < 0:
        return "--:--"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class _ProgressState:
    """Mutable state for the progress display."""

    def __init__(self, database: str) -> None:
        self.database = database
        self.sp_current = 0
        self.sp_total = 0
        self.bytes_processed = 0
        self.bytes_total = 0
        self.current_sp_name = ""
        self.phase = ""  # "chunking" | "embedding" | ""
        self.chunk_count = 0
        self.start_time = time.perf_counter()

    def elapsed(self) -> float:
        return time.perf_counter() - self.start_time

    def eta(self) -> float:
        if self.sp_current == 0 or self.sp_total == 0:
            return -1
        elapsed = self.elapsed()
        rate = self.sp_current / elapsed
        remaining = self.sp_total - self.sp_current
        return remaining / rate if rate > 0 else -1

    def progress_pct(self) -> int:
        if self.sp_total == 0:
            return 0
        return int(100 * self.sp_current / self.sp_total)


def _build_panel(state: _ProgressState, spinner_frame: str) -> Panel:
    """Build the Rich Panel for the current progress state."""
    lines: list[Text | str] = []

    # Progress bar
    pct = state.progress_pct()
    filled = int(pct / 100 * _PROGRESS_BAR_WIDTH)
    if filled < _PROGRESS_BAR_WIDTH:
        bar = "━" * filled + "╸" + "░" * (_PROGRESS_BAR_WIDTH - filled - 1)
    else:
        bar = "━" * _PROGRESS_BAR_WIDTH
    lines.append(
        Text.from_markup(
            f"  Progress: [bold]{state.sp_current}/{state.sp_total} SPs[/bold]  "
            f"[blue]{bar}[/blue]  {pct}%"
        )
    )

    # Data progress
    lines.append(
        Text.from_markup(
            f"  Data:     {_format_bytes(state.bytes_processed)} / "
            f"{_format_bytes(state.bytes_total)}"
        )
    )

    # Time
    elapsed_str = _format_time(state.elapsed())
    eta_str = _format_time(state.eta())
    lines.append(Text.from_markup(f"  Time:     {elapsed_str} elapsed │ ~{eta_str} remaining"))

    # Separator
    lines.append(Text("  " + "─" * 60))

    # Current SP
    if state.current_sp_name:
        lines.append(Text.from_markup(f"  [bold cyan]⚡ {state.current_sp_name}[/bold cyan]"))

        # Chunking phase
        if state.phase == "chunking":
            chunk_line = f"     [{spinner_frame}] [yellow]Chunking[/yellow]  → processing..."
            lines.append(Text.from_markup(chunk_line))
            lines.append(Text.from_markup("     [ ] Embedding"))
        elif state.phase == "embedding":
            chunk_info = f"{state.chunk_count} chunks" if state.chunk_count else "done"
            lines.append(Text.from_markup(f"     [green]✓[/green] Chunking   → {chunk_info}"))
            embed_line = f"     [{spinner_frame}] [yellow]Embedding[/yellow] → {state.chunk_count}"
            lines.append(Text.from_markup(embed_line))
        else:
            lines.append(Text.from_markup("     [ ] Chunking"))
            lines.append(Text.from_markup("     [ ] Embedding"))
    else:
        lines.append(Text.from_markup("  [dim]Discovering procedures...[/dim]"))

    content = Group(*lines)
    return Panel(
        content,
        title=f"[bold]KB Bootstrap: {state.database}[/bold]",
        subtitle=f"[dim]{_get_hardware_line()}[/dim]",
        border_style="blue",
        padding=(0, 1),
    )


@contextmanager
def _progress_context(  # noqa: PLR0915
    database: str = "",
) -> Iterator[kb_indexer.ProgressCallback]:
    """Render a Rich panel on stderr and yield a callback that drives it."""
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.CRITICAL)
    set_suppress_info_events(True)

    # Suppress all transformer/tokenizer warnings that break the Live display
    _prev_tv = os.environ.get("TRANSFORMERS_VERBOSITY")
    _prev_tp = os.environ.get("TOKENIZERS_PARALLELISM")
    _prev_hf = os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS")
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

    # Suppress specific loggers that might output during embedding
    for logger_name in ("transformers", "sentence_transformers", "tokenizers"):
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)

    console = Console(stderr=True, force_terminal=True)
    state = _ProgressState(database or "...")
    spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    spinner_idx = [0]

    def _render() -> Panel:
        spinner_idx[0] = (spinner_idx[0] + 1) % len(spinner_chars)
        return _build_panel(state, spinner_chars[spinner_idx[0]])

    try:
        with Live(_render(), console=console, refresh_per_second=4, transient=True) as live:

            def _on_progress(event: kb_indexer.ProgressEvent) -> None:
                stage = event.get("stage")
                if stage == "total_update":
                    total = event.get("total")
                    proc_total = event.get("proc_total", 0)
                    if isinstance(total, int):
                        state.bytes_total = total
                    if proc_total:
                        state.sp_total = proc_total
                elif stage == "proc_start":
                    state.current_sp_name = str(event.get("name", ""))
                    state.sp_current = int(event.get("proc_index", 0))
                    state.sp_total = int(event.get("proc_total", state.sp_total))
                    state.phase = ""
                    state.chunk_count = 0
                    # Update database from first event if not set
                    if state.database == "...":
                        state.database = str(event.get("database", "..."))
                elif stage == "phase":
                    phase = event.get("phase", "")
                    detail = event.get("detail")
                    state.phase = str(phase)
                    if phase == "embedding" and detail:
                        # detail is like "200 chunks"
                        with suppress(ValueError, IndexError):
                            state.chunk_count = int(str(detail).split()[0])
                elif stage == "proc_done":
                    units = event.get("work_units", 0)
                    if isinstance(units, int):
                        state.bytes_processed += units

                live.update(_render())

            yield _on_progress
    finally:
        set_suppress_info_events(False)
        root_logger.setLevel(previous_level)
        # Restore environment variables
        for key, prev in [
            ("TRANSFORMERS_VERBOSITY", _prev_tv),
            ("TOKENIZERS_PARALLELISM", _prev_tp),
            ("HF_HUB_DISABLE_PROGRESS_BARS", _prev_hf),
        ]:
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev


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

    db_label = dbs[0] if len(dbs) == 1 else f"{len(dbs)} databases"
    with _progress_context(database=db_label) as on_progress:
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
