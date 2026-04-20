"""Typer CLI for nz-workbench.

Commands:
- ``kb-bootstrap``  index all PROD procedures (once, ~2 h on CPU).
- ``kb-refresh``    re-index a single procedure.
- ``kb-refresh-cron`` scan _V_PROCEDURE and re-index changed procedures (opt-in).
- ``kb-export``     tar.zst the local KB for portability.
- ``kb-import``     restore an exported KB.
- ``analyze``       run the REN analyzer for a given REN folder.
- ``migrate``       execute the clone + rewrite phase for a REN manifest.
- ``test``          run baseline and comparison tests for a REN.
- ``doc-update``    append/update docs/procedures/<SP>.md entries.
- ``explain``       generate a pedagogical mapping for one procedure.
- ``search``        semantic + structural search on the KB.
- ``serve``         run the MCP server over stdio.
- ``version``       print the installed nz-workbench version.
"""

from __future__ import annotations

from pathlib import Path

import typer

from nz_workbench import __version__

app = typer.Typer(
    name="nz-workbench",
    help="AI-assisted workbench for IBM Netezza procedure maintenance.",
    no_args_is_help=True,
    add_completion=False,
)


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
    typer.echo(f"[stub] kb-bootstrap databases={databases} top_n={top_n}")
    raise typer.Exit(code=0)


@app.command("kb-refresh")
def kb_refresh_cmd(
    target: str = typer.Argument(..., help="Fully qualified procedure name (DB.SCHEMA.NAME)."),
) -> None:
    """Re-index a single procedure when you know it changed in PROD."""
    typer.echo(f"[stub] kb-refresh {target}")
    raise typer.Exit(code=0)


@app.command("kb-refresh-cron")
def kb_refresh_cron_cmd() -> None:
    """Scan _V_PROCEDURE.LASTALTERTIME and re-index changed procedures (opt-in cron)."""
    typer.echo("[stub] kb-refresh-cron")
    raise typer.Exit(code=0)


@app.command("kb-export")
def kb_export_cmd(
    out: Path = typer.Argument(..., help="Output archive path (e.g. kb.tar.zst)."),
) -> None:
    """Export the local KB as a portable archive."""
    typer.echo(f"[stub] kb-export → {out}")
    raise typer.Exit(code=0)


@app.command("kb-import")
def kb_import_cmd(
    archive: Path = typer.Argument(..., help="Archive to import (from kb-export)."),
) -> None:
    """Import a KB archive into this machine's .nz-workbench/ directory."""
    typer.echo(f"[stub] kb-import ← {archive}")
    raise typer.Exit(code=0)


@app.command("analyze")
def analyze_cmd(
    ren_folder: Path = typer.Argument(..., help="Path to ren/REN_<N>/ with source.md inside."),
) -> None:
    """Analyze a REN and produce analysis.yaml + clarifications.md."""
    typer.echo(f"[stub] analyze {ren_folder}")
    raise typer.Exit(code=0)


@app.command("migrate")
def migrate_cmd(
    ren_folder: Path = typer.Argument(..., help="Path to ren/REN_<N>/ with manifest.yaml."),
    dry_run: bool = typer.Option(True, "--dry-run/--confirm", help="Dry-run or commit to DESA_*."),
) -> None:
    """Clone the procedures listed in the manifest into DESA_* with rewrite rules."""
    typer.echo(f"[stub] migrate {ren_folder} dry_run={dry_run}")
    raise typer.Exit(code=0)


@app.command("test")
def test_cmd(
    ren_folder: Path = typer.Argument(..., help="Path to ren/REN_<N>/."),
    phase: str = typer.Option("both", "--phase", help="baseline | comparison | both"),
) -> None:
    """Run baseline (phase 6) and/or comparison (phase 8) for the REN."""
    typer.echo(f"[stub] test {ren_folder} phase={phase}")
    raise typer.Exit(code=0)


@app.command("doc-update")
def doc_update_cmd(
    ren_folder: Path = typer.Argument(..., help="Path to ren/REN_<N>/ after approval."),
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
    from nz_workbench.mcp_server import run_stdio_server

    run_stdio_server()
