# Maintainability

## Function and module size

- **Functions**: target ≤ 30 lines, hard limit 50.
- **Function parameters**: target ≤ 3, hard limit 4. Beyond that, use a dataclass.
- **Modules**: target ≤ 300 lines, hard limit 500. Beyond that, split.

`ruff` is configured with `PLR0913` (too-many-arguments) and `PLR0915` (too-many-statements) enabled. Exceptions require `# noqa` with a comment explaining why.

## Abstraction rules

- No new abstraction without **three real usages**. If you only have one or two, inline.
- No "helper for possible future use". Delete code that is not called.
- Prefer duplication over premature coupling for the first two sites; on the third, extract.

## Dependency hygiene

- Every new runtime dependency requires an ADR under `docs/adr/`.
- Dev dependencies (`ruff`, `mypy`, `pytest`, `hypothesis`) do not require an ADR but must be pinned to a minor version.
- Dependencies are reviewed quarterly for updates and security advisories.

## Type hints

- Every public function and method has complete type hints (parameters and return).
- `mypy --strict` must pass on all production modules.
- Tests may use `disable_error_code = ["explicit-any"]` for fakes.
- `cast()` is acceptable at MCP / JSON boundaries where mypy cannot infer through protocols. Add a comment when it is not obvious.

## Imports

- Absolute imports everywhere (`from nz_workbench.kb.chunker import chunk`).
- Third-party imports grouped separately from stdlib and local.
- Side-effect imports (registering a module with a framework) must carry `# noqa: F401` and a comment explaining the side effect.

## Docstrings

- Module-level docstring required on every file.
- Public class and function docstrings explain the contract in one paragraph.
- Private helpers may skip the docstring if the name is self-explanatory.
- No docstring ever describes implementation details that belong in comments or commit messages.

## Constants

- Module-level constants use `SCREAMING_SNAKE_CASE` with `Final` type annotation:
  ```python
  _MAX_CHUNK_TOKENS: Final[int] = 400
  ```
- Magic numbers inside functions are an antipattern. Extract to named constants.

## Error handling

- Never catch `BaseException`.
- Catch `Exception` only at the outermost boundary (CLI, MCP server) and always wrap in a typed error from `nz_workbench.errors`.
- Re-raise with `from exc` to preserve the cause chain.
- Ban `except: pass` entirely.

## Logging

- Use `structlog` everywhere. No `print()` in production code.
- Every log statement has a stable event name:
  ```python
  _LOG.info("kb_index_procedure", database=db, schema=sch, proc=name, duration_ms=t)
  ```
- Log at `INFO` for expected lifecycle events, `WARNING` for recoverable issues, `ERROR` for failures.
- **Never** log to stdout when running as MCP server. `mcp_server.py` calls `configure_logging_for_stdio()` from the same pattern used in `nz-mcp` to route structlog to stderr.

## Configuration

- No hardcoded paths, database names, or magic strings for the user's environment.
- Configurable values go in `config.py` with sensible defaults, overridable via environment variables prefixed `NZ_WORKBENCH_*` or config file.
- Test thresholds and secrets have no defaults — they fail loudly if unset.
