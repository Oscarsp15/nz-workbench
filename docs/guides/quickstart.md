# Quickstart

Five minutes from zero to a working `nz-workbench` against your Netezza.

## Prerequisites

1. Python 3.11 or newer.
2. `nz-mcp` installed and configured: https://github.com/Oscarsp15/nz-mcp.
3. Claude Code CLI or Claude Desktop.

## Install

```bash
pipx install git+https://github.com/Oscarsp15/nz-workbench.git
# OR for development:
git clone https://github.com/Oscarsp15/nz-workbench.git
cd nz-workbench
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # Linux/macOS
pip install -e ".[dev]"
```

## Bootstrap your starter files

Templates ship in git; your actual data stays local.

```bash
cp docs/learning-log.md.template         docs/learning-log.md
cp docs/technical-decisions.md.template  docs/technical-decisions.md
cp docs/side-effects-catalog.md.template docs/side-effects-catalog.md
```

## Configure Claude Code

Add to `~/.claude.json` (global) or `.mcp.json` (project-local):

```json
{
  "mcpServers": {
    "nz-workbench": {
      "command": "nz-workbench",
      "args": ["serve"]
    }
  }
}
```

## Index production procedures (one-time, ~2h CPU)

```bash
nz-workbench kb-bootstrap --databases PROD_DB1,PROD_DB2
```

Zero Claude tokens. Runs BGE-M3 on your local CPU. Output under `.nz-workbench/`.

## Start your first REN

```bash
# Copy the template
cp -r ren/_TEMPLATE ren/REN_12345
# Paste the REN document into ren/REN_12345/source.md
```

Open Claude Code in the repo and say:

> "Analyze REN 12345."

The AI will:

1. Parse the REN.
2. Search the knowledge base.
3. Either produce `analysis.yaml` cleanly, or emit `clarifications.md` with questions you must answer before proceeding.

Follow the phases documented in [`../architecture/ren-lifecycle.md`](../architecture/ren-lifecycle.md).

## Troubleshooting

- **`nz-mcp` not found**: install it (`pipx install nz-mcp` or source), or set `NZ_MCP_BIN` to its full path.
- **Embedder download is slow**: first bootstrap downloads ~2.3 GB of model weights. Run it on a good connection.
- **`.nz-workbench/` grows large**: ~1–2 GB for 6,000 procedures is expected. Add it to your disk-usage watch list.
- **Clarifications blocker**: the AI never guesses. If phase 3 is taking time, it's because the REN has ambiguity — that's the feature, not the bug.
