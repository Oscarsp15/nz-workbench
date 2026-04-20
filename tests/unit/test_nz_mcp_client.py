from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any

import pytest

from nz_workbench.errors import NzMcpUnavailableError
from nz_workbench.nz_mcp_client.client import NzMcpClient


@dataclass
class _FakeProc:
    stdin: io.StringIO | None
    stdout: io.StringIO | None
    terminated: bool = False
    killed: bool = False
    waited: bool = False

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> None:
        _ = timeout
        self.waited = True


@pytest.mark.unit
def test_nz_mcp_client_initialize_and_call(monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare server outputs: initialize response (id=1), notification (no id),
    # tools/call response (id=2), shutdown response (id=3).
    out_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "nz-mcp"}}}),
        "not-json-noise",
        json.dumps({"jsonrpc": "2.0", "method": "notifications/logging", "params": {"msg": "x"}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [{"type": "text", "text": "ok"}],
                    "structuredContent": {"result": {"ok": True, "value": 1}},
                    "isError": False,
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}),
    ]
    fake = _FakeProc(stdin=io.StringIO(), stdout=io.StringIO("\n".join(out_lines) + "\n"))

    def fake_popen(*_args: Any, **_kwargs: Any) -> _FakeProc:
        return fake

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    client = NzMcpClient(bin_path="nz-mcp")
    client.start()
    res = client.call("nz_list_procedures", {"database": "PROD_X"})
    assert res.ok is True
    assert res.result == {"ok": True, "value": 1}

    client.stop()
    assert fake.terminated or fake.killed

    assert fake.stdin is not None
    written = fake.stdin.getvalue().splitlines()
    assert any(json.loads(line).get("method") == "initialize" for line in written)
    assert any(json.loads(line).get("method") == "tools/call" for line in written)


@pytest.mark.unit
def test_nz_mcp_client_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    out_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "error": {"code": "TOOL_ERR", "message": "nope", "data": {"x": 1}},
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}),
    ]
    fake = _FakeProc(stdin=io.StringIO(), stdout=io.StringIO("\n".join(out_lines) + "\n"))

    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: fake)

    client = NzMcpClient(bin_path="nz-mcp")
    client.start()
    res = client.call("nz_list_procedures", {"database": "PROD_X"})
    assert res.ok is False
    assert res.error_code == "TOOL_ERR"
    assert res.error_context == {"x": 1}


@pytest.mark.unit
def test_nz_mcp_client_start_raises_on_popen_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> Any:
        raise OSError("nope")

    monkeypatch.setattr("subprocess.Popen", boom)
    client = NzMcpClient(bin_path="nz-mcp")
    with pytest.raises(NzMcpUnavailableError):
        client.start()


@pytest.mark.unit
def test_nz_mcp_client_start_raises_when_stdio_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeProc(stdin=None, stdout=io.StringIO(""))

    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: fake)
    client = NzMcpClient(bin_path="nz-mcp")
    with pytest.raises(NzMcpUnavailableError):
        client.start()
    assert fake.terminated is True


@pytest.mark.unit
def test_nz_mcp_client_start_raises_on_initialize_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": "INIT", "message": "no"}}),
    ]
    fake = _FakeProc(stdin=io.StringIO(), stdout=io.StringIO("\n".join(out_lines) + "\n"))
    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: fake)
    client = NzMcpClient(bin_path="nz-mcp")
    with pytest.raises(NzMcpUnavailableError):
        client.start()


@pytest.mark.unit
def test_nz_mcp_client_wraps_non_dict_results(monkeypatch: pytest.MonkeyPatch) -> None:
    out_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [], "structuredContent": {}, "isError": False},
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}),
    ]
    fake = _FakeProc(stdin=io.StringIO(), stdout=io.StringIO("\n".join(out_lines) + "\n"))
    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: fake)
    client = NzMcpClient(bin_path="nz-mcp")
    client.start()
    res = client.call("nz_list_procedures", {"database": "PROD_X"})
    assert res.ok is True
    assert res.result == {}


@pytest.mark.unit
def test_call_extracts_structured_content_error(monkeypatch: pytest.MonkeyPatch) -> None:
    out_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [{"type": "text", "text": "err"}],
                    "structuredContent": {
                        "error": {"code": "INVALID_INPUT", "context": {"detail": "schema required"}}
                    },
                    "isError": True,
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}),
    ]
    fake = _FakeProc(stdin=io.StringIO(), stdout=io.StringIO("\n".join(out_lines) + "\n"))
    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: fake)
    client = NzMcpClient(bin_path="nz-mcp")
    client.start()
    res = client.call("nz_list_procedures", {"database": "PROD_X"})
    assert res.ok is False
    assert res.error_code == "INVALID_INPUT"
    assert res.error_context == {"detail": "schema required"}


@pytest.mark.unit
def test_call_is_error_flag_without_structured_content(monkeypatch: pytest.MonkeyPatch) -> None:
    out_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [{"type": "text", "text": "no structured"}],
                    "isError": True,
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}),
    ]
    fake = _FakeProc(stdin=io.StringIO(), stdout=io.StringIO("\n".join(out_lines) + "\n"))
    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: fake)
    client = NzMcpClient(bin_path="nz-mcp")
    client.start()
    res = client.call("nz_list_procedures", {"database": "PROD_X"})
    assert res.ok is False
    assert res.error_code == "TOOL_ERROR"


@pytest.mark.unit
def test_call_fallback_parses_text_content_json(monkeypatch: pytest.MonkeyPatch) -> None:
    out_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"result": {"schemas": [{"name": "DBO"}]}}),
                        }
                    ],
                    "isError": False,
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}),
    ]
    fake = _FakeProc(stdin=io.StringIO(), stdout=io.StringIO("\n".join(out_lines) + "\n"))
    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: fake)
    client = NzMcpClient(bin_path="nz-mcp")
    client.start()
    res = client.call("nz_list_schemas", {"database": "PROD_X"})
    assert res.ok is True
    assert res.result == {"schemas": [{"name": "DBO"}]}


@pytest.mark.unit
def test_call_unknown_shape_returns_inner_as_result(monkeypatch: pytest.MonkeyPatch) -> None:
    out_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [],
                    "structuredContent": {"hello": "world"},
                    "isError": False,
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}),
    ]
    fake = _FakeProc(stdin=io.StringIO(), stdout=io.StringIO("\n".join(out_lines) + "\n"))
    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: fake)
    client = NzMcpClient(bin_path="nz-mcp")
    client.start()
    res = client.call("nz_any", {})
    assert res.ok is True
    assert res.result == {"hello": "world"}


@pytest.mark.unit
def test_nz_mcp_client_read_one_ignores_non_dict_json(monkeypatch: pytest.MonkeyPatch) -> None:
    out_lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps([1, 2, 3]),
        json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"x": 1}}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}),
    ]
    fake = _FakeProc(stdin=io.StringIO(), stdout=io.StringIO("\n".join(out_lines) + "\n"))
    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: fake)
    client = NzMcpClient(bin_path="nz-mcp")
    client.start()
    res = client.call("nz_list_procedures", {"database": "PROD_X"})
    assert res.ok is True
    assert res.result == {"x": 1}
