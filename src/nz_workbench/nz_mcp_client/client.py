"""Client to the ``nz-mcp`` MCP server. Single instance per process, lazy start.

This wrapper intentionally keeps a narrow surface area:
- Start ``nz-mcp serve`` as a subprocess (stdio transport).
- Call tools by name with JSON arguments.

The MCP protocol is JSON-RPC over newline-delimited JSON on stdin/stdout.
"""

from __future__ import annotations

import json
import subprocess
import threading
from contextlib import suppress
from dataclasses import dataclass
from typing import IO, Any, Final

import structlog

from nz_workbench import __version__
from nz_workbench.errors import NzMcpUnavailableError

_log = structlog.get_logger(__name__)

_JSONRPC_VERSION: Final[str] = "2.0"


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Structured result of an MCP tool call."""

    ok: bool
    result: dict[str, Any] | None
    error_code: str | None
    error_context: dict[str, Any] | None


class NzMcpClient:
    """Connects to ``nz-mcp serve`` as a subprocess via stdio JSON-RPC."""

    def __init__(self, bin_path: str = "nz-mcp") -> None:
        self._bin_path = bin_path
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._next_id = 1

    def start(self) -> None:
        """Spawn the nz-mcp subprocess and perform MCP initialize."""

        if self._proc is not None:
            return

        try:
            proc = subprocess.Popen(  # noqa: S603
                [self._bin_path, "serve"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,  # inherit stderr so errors are visible
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise NzMcpUnavailableError("failed to start nz-mcp", bin_path=self._bin_path) from exc

        if proc.stdin is None or proc.stdout is None:
            proc.terminate()
            raise NzMcpUnavailableError("nz-mcp stdio not available", bin_path=self._bin_path)

        self._proc = proc

        init = self._request(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nz-workbench", "version": __version__},
            },
        )
        if "error" in init:
            self.stop()
            raise NzMcpUnavailableError("nz-mcp initialize failed", error=init["error"])

        # Per MCP handshake, send the initialized notification.
        self._notify(method="notifications/initialized", params={})
        _log.info("nz_mcp_started", bin_path=self._bin_path)

    def stop(self) -> None:
        """Gracefully close the subprocess."""

        proc = self._proc
        self._proc = None
        if proc is None:
            return

        with suppress(Exception):
            self._request(method="shutdown", params={})
            self._notify(method="exit", params={})
        with suppress(Exception):
            proc.terminate()
            proc.wait(timeout=2)
        with suppress(Exception):
            proc.kill()

    def call(self, tool: str, arguments: dict[str, Any]) -> ToolResult:
        """Invoke a tool by name and return its structured result."""

        self.start()
        payload = self._request(
            method="tools/call",
            params={"name": tool, "arguments": arguments},
        )

        if "error" in payload:
            err = payload["error"] or {}
            code = err.get("code")
            data = err.get("data")
            return ToolResult(
                ok=False,
                result=None,
                error_code=str(code) if code is not None else None,
                error_context=data,
            )

        result = payload.get("result")
        # We expect tool implementations to return a JSON object.
        if isinstance(result, dict):
            return ToolResult(ok=True, result=result, error_code=None, error_context=None)
        if result is None:
            return ToolResult(ok=True, result={}, error_code=None, error_context=None)
        return ToolResult(ok=True, result={"result": result}, error_code=None, error_context=None)

    # ----- JSON-RPC helpers -----
    def _stdin(self) -> IO[str]:
        if self._proc is None or self._proc.stdin is None:
            raise NzMcpUnavailableError("nz-mcp not started", bin_path=self._bin_path)
        return self._proc.stdin

    def _stdout(self) -> IO[str]:
        if self._proc is None or self._proc.stdout is None:
            raise NzMcpUnavailableError("nz-mcp not started", bin_path=self._bin_path)
        return self._proc.stdout

    def _request(self, *, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            msg = {"jsonrpc": _JSONRPC_VERSION, "id": req_id, "method": method, "params": params}
            self._send(msg)
            while True:
                incoming = self._read_one()
                if incoming.get("id") == req_id:
                    return incoming

    def _notify(self, *, method: str, params: dict[str, Any]) -> None:
        with self._lock:
            msg = {"jsonrpc": _JSONRPC_VERSION, "method": method, "params": params}
            self._send(msg)

    def _send(self, msg: dict[str, Any]) -> None:
        data = json.dumps(msg, ensure_ascii=False)
        stdin = self._stdin()
        stdin.write(data + "\n")
        stdin.flush()

    def _read_one(self) -> dict[str, Any]:
        line = self._stdout().readline()
        if line == "":
            raise NzMcpUnavailableError(
                "nz-mcp closed stdout unexpectedly", bin_path=self._bin_path
            )
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            # Some servers may emit non-JSON lines on stdout; treat as noise.
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}


__all__ = ["NzMcpClient", "ToolResult"]
