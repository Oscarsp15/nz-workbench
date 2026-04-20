"""Allow ``python -m nz_workbench`` to invoke the CLI."""

from __future__ import annotations

from nz_workbench.cli import app

if __name__ == "__main__":
    app()
