# Secrets handling

## Never committed

- `profiles.toml` (Netezza profiles — host, port, db, user, mode).
- Passwords — live in the OS keyring via `nz-mcp`, never in files.
- `.env`, `.env.local`, any file matching `*.env`.
- Credential files (`credentials.json`, `secrets/`).
- REN content that contains internal business identifiers considered confidential.

All of these are in `.gitignore`. Pre-commit hooks must catch accidental additions.

## Provided by `nz-mcp`

This project does not handle Netezza authentication directly. It invokes `nz-mcp` as an MCP subprocess; `nz-mcp` reads its own profiles and keyring entries.

Effect: this repo never sees a password, host, or raw credential. It receives structured responses from `nz-mcp` and never stores them.

## Local state with sensitive content

`.nz-workbench/` contains:

- Vector embeddings of procedure bodies.
- Structural metadata about procedures.
- Cached LLM outputs.
- Optionally: cached copies of procedure DDLs for faster access.

This folder **may contain business logic** from your organization. It must not be shared externally. Treat it as equivalent to the procedure source itself.

For portability (moving to another machine), the export command encrypts the archive:

```bash
nz-workbench kb-export --encrypt out.tar.zst.age
# requires age or equivalent; passphrase prompted
```

Do not commit exported archives.

## Log sanitization

Logs are produced by the MCP server (stderr) and by the CLI (stderr by default). They must never include:

- Passwords.
- Full SQL body of procedures (leak risk).
- Output rows from PROD queries (PII).

Use `nz_mcp.logging_utils.sanitize()` pattern from `nz-mcp` when composing error messages that may contain driver output. The rule is: log identifiers and shapes, never values.

## REN folder content

`ren/REN_<N>/` folders are committed to git. They contain the REN source, analysis, diffs, and summaries. Before committing the first REN to a new repo, verify that:

- The REN source does not embed PII samples.
- The `conversation.md` (optional CLI transcript) is sanitized of any password the user typed by mistake.
- `test_report.md` does not contain full row dumps — only aggregates and small samples.

## Reporting a leak

If credentials or business data are accidentally committed:

1. Do NOT amend the commit — the history is already pushed.
2. Rotate the affected credential immediately.
3. Use `git filter-repo` or a BFG-style tool to purge the blob from history.
4. Force-push is acceptable in this specific case; document the cleanup in `CHANGELOG.md` under `Security`.
5. Notify the team if the repo is shared.
