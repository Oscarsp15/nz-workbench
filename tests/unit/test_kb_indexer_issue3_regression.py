from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from nz_workbench.kb import indexer
from nz_workbench.nz_mcp_client import ToolResult


class _FailSchemasClient:
    def __init__(self, bin_path: str) -> None:
        assert bin_path
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        return

    def call(self, tool: str, arguments: dict[str, Any]) -> ToolResult:
        if tool == "nz_list_schemas":
            return ToolResult(
                ok=False,
                result=None,
                error_code="INVALID_INPUT",
                error_context={"tool": tool, "arguments": arguments},
            )
        return ToolResult(ok=False, result=None, error_code="UNEXPECTED", error_context=None)


@pytest.mark.unit
def test_bootstrap_propagates_schema_list_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = type(
        "Cfg",
        (),
        {"state_dir": tmp_path, "nz_mcp_bin": "nz-mcp", "embedder_model": "BAAI/bge-m3"},
    )()
    monkeypatch.setattr(indexer, "load_config", lambda: cfg)
    monkeypatch.setattr(indexer, "NzMcpClient", _FailSchemasClient)

    report = indexer.bootstrap(["PROD_X"])
    assert report.errors
    assert any("failed to list schemas" in e for e in report.errors)


@pytest.mark.unit
def test_parse_proc_list_accepts_items_without_schema() -> None:
    raw = [{"name": "SP1", "arguments": "(DATE)"}, {"name": "SP2", "arguments": "()"}]
    procs = indexer._parse_proc_list("PROD_X", "DBO", raw)
    assert [p.schema for p in procs] == ["DBO", "DBO"]
