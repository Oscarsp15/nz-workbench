from __future__ import annotations

import pytest

from nz_workbench.kb.indexer import _extract_references, _fallback_regex_references
from nz_workbench.nz_mcp_client import ToolResult


@pytest.mark.unit
def test_fallback_regex_references_finds_reads_writes_calls() -> None:
    ddl = """
    BEGIN
      INSERT INTO DBO.T1 VALUES (1);
      UPDATE DBO.T2 SET a=1;
      DELETE FROM DBO.T3;
      SELECT * FROM DBO.T4 JOIN DBO.T5 ON 1=1;
      CALL DBO.SP_X();
      EXEC DBO.SP_Y;
    END;
    """
    refs = _fallback_regex_references(ddl)
    kinds = {r.kind for r in refs}
    assert {"read", "write", "call"}.issubset(kinds)


@pytest.mark.unit
def test_extract_references_parses_tool_payload() -> None:
    res = ToolResult(
        ok=True,
        result={
            "references": [
                {
                    "kind": "read",
                    "op": "SELECT",
                    "ref_database": None,
                    "ref_schema": "DBO",
                    "ref_object": "T",
                    "line_from": 1,
                    "line_to": 2,
                }
            ]
        },
        error_code=None,
        error_context=None,
    )
    refs = _extract_references(res)
    assert len(refs) == 1
    assert refs[0].kind == "read"
    assert refs[0].ref_schema == "DBO"
