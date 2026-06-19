"""MCP transport seam shared by the real Cortex/AutoDev providers.

The providers depend only on the small synchronous :class:`ToolCaller` protocol
(``call_tool(name, arguments) -> dict``). This keeps the request-shaping and
response-mapping logic — the part that actually matters — fully unit-testable
with a fake caller, and isolates the async MCP transport behind one class.

:class:`MCPToolCaller` is the production implementation backed by the official
``mcp`` SDK. MCP is async and stream-oriented while the Mars engine is
synchronous, so the caller runs a dedicated event loop in a background thread
and bridges each call across it, keeping a single session open for a workspace's
whole lifecycle (create → run → test → diff → cleanup).

The ``mcp`` package is an optional dependency: it is imported lazily so Mars
installs and tests without it.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ToolCaller(Protocol):
    """Minimal synchronous MCP tool interface the providers program against."""

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...

    def close(self) -> None: ...


@dataclass
class MCPServerConfig:
    """How to reach an MCP server.

    Exactly one transport is used. ``command`` selects stdio (spawn a local
    server process); ``url`` selects HTTP (streamable-http by default, or SSE).
    Values typically come from env, e.g. ``MARS_AUTODEV_MCP_URL`` or
    ``MARS_AUTODEV_MCP_COMMAND``.
    """

    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    transport: str = "streamable-http"  # "streamable-http" | "sse" (url only)
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        if not self.command and not self.url:
            raise ValueError("MCPServerConfig requires either `command` (stdio) or `url` (http)")


def _result_to_dict(result: Any) -> dict[str, Any]:
    """Normalize an MCP ``CallToolResult`` into a plain dict.

    Prefers ``structuredContent`` (structured tool output); otherwise parses the
    first text content block as JSON. Raises on tool-reported errors.
    """
    if getattr(result, "isError", False):
        raise RuntimeError(f"MCP tool reported an error: {_first_text(result)}")
    structured = getattr(result, "structuredContent", None)
    if structured:
        # SDK may wrap a non-object payload under a "result" key.
        return structured.get("result", structured) if isinstance(structured, dict) else structured
    text = _first_text(result)
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


def _first_text(result: Any) -> str:
    for block in getattr(result, "content", None) or []:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


class MCPToolCaller:
    """Synchronous façade over an async MCP ``ClientSession``.

    Owns a background thread + event loop; the session and transport stay open
    until :meth:`close`. Each :meth:`call_tool` is marshalled onto that loop.
    """

    def __init__(self, config: MCPServerConfig) -> None:
        import asyncio  # local imports: keep module import-light

        self._config = config
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._session: Any = None
        self._stack: Any = None
        self._thread = threading.Thread(target=self._run_loop, name="mars-mcp", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._startup_error is not None:
            raise self._startup_error

    def _run_loop(self) -> None:
        import asyncio

        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except BaseException as exc:  # surface connection failures to the caller
            self._startup_error = exc
            self._ready.set()
            return
        self._ready.set()
        self._loop.run_forever()

    async def _connect(self) -> None:
        from contextlib import AsyncExitStack

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        cfg = self._config
        self._stack = AsyncExitStack()
        if cfg.url:
            if cfg.transport == "sse":
                from mcp.client.sse import sse_client

                read, write = await self._stack.enter_async_context(
                    sse_client(cfg.url, headers=cfg.headers or None)
                )
            else:
                from mcp.client.streamable_http import streamablehttp_client

                read, write, _ = await self._stack.enter_async_context(
                    streamablehttp_client(cfg.url, headers=cfg.headers or None)
                )
        else:
            params = StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env or None)
            read, write = await self._stack.enter_async_context(stdio_client(params))

        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        async def _invoke() -> dict[str, Any]:
            result = await self._session.call_tool(name, arguments)
            return _result_to_dict(result)

        future = asyncio.run_coroutine_threadsafe(_invoke(), self._loop)
        return future.result(timeout=self._config.timeout_seconds)

    def close(self) -> None:
        import asyncio

        if self._loop.is_closed():
            return

        async def _shutdown() -> None:
            if self._stack is not None:
                await self._stack.aclose()

        try:
            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop).result(timeout=30)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()
