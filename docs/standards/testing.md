# Testing standards

## Coverage

- **Global**: ≥ 85% from day 1. Same standard as `nz-mcp`.
- **Security-critical modules** (`migrator/rules.py`, `migrator/side_effects.py`): ≥ 95%.
- Coverage is reported in CI; PRs that lower the threshold are blocked.

## Test structure

```
tests/
├── conftest.py                # shared fixtures
├── unit/                      # fast, isolated, no Netezza
│   ├── test_kb_chunker.py
│   ├── test_migrator_rules.py
│   ├── test_analyzer_ren_parser.py
│   └── …
└── integration/               # hits real services (MCP, Netezza) — opt-in
    ├── test_bootstrap_smoke.py
    ├── test_ren_end_to_end.py
    └── …
```

## Markers

- `@pytest.mark.unit` — default, fast.
- `@pytest.mark.integration` — requires a live Netezza profile. Skipped in CI unless `NZ_WORKBENCH_RUN_INTEGRATION=1`.
- `@pytest.mark.slow` — takes more than 5 seconds.
- `@pytest.mark.contract` — validates the wire contract between modules or with `nz-mcp`.
- `@pytest.mark.adversarial` — security-focused, tries to bypass rules / guards.

## Fixtures

Shared fixtures live in `tests/conftest.py`:

- `tmp_kb_home` — a pristine `.nz-workbench/` directory per test.
- `tmp_profiles` — a `profiles.toml` with dev and prod profiles.
- `fake_nz_mcp_client` — stub that responds to MCP tool calls deterministically.

## Integration tests

Require a local Netezza profile and an MCP installation of `nz-mcp`. Enabled with `NZ_WORKBENCH_RUN_INTEGRATION=1`.

Environment variables used:

- `NZ_WORKBENCH_TEST_DATABASE` (default `DESA_MODELOS`)
- `NZ_WORKBENCH_TEST_SCHEMA` (default `DBO`)
- `NZ_WORKBENCH_TEST_PROCEDURE` (default `AGRUPAR_ALERTAS`)
- `NZ_WORKBENCH_TEST_FECCORTE` (default previous month-end)

Integration tests that mutate state must use the sandbox schema and always clean up after themselves, even if the test fails.

## Hypothesis property-based tests

For parsing and rule modules (`analyzer/ren_parser.py`, `migrator/rules.py`, `kb/chunker.py`), prefer property-based tests using `hypothesis` over hand-crafted examples where possible.

Example shape:

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=200))
def test_chunker_does_not_lose_content(body: str) -> None:
    chunks = chunk(body)
    assert "".join(chunks).replace(" ", "") == body.replace(" ", "")
```

## What not to test

- The behavior of `nz-mcp` itself. We trust it. Integration tests that hit Netezza exercise it implicitly.
- `sentence-transformers` or `chromadb` internals.
- Claude LLM outputs (non-deterministic). Tests that call the LLM are always in `@integration` and verify shape, not content.
