from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Any, Dict, List

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, Tool


class MCPToolClient:
    """SSE-backed MCP client used by the API for dynamic tool discovery and execution."""

    def __init__(self, server_url: str, connect_retries: int = 20, retry_delay_seconds: float = 1.5):
        self.server_url = server_url
        self.connect_retries = connect_retries
        self.retry_delay_seconds = retry_delay_seconds

        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: List[Tool] = []
        self._openai_tools: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Connect to MCP server and fetch tools dynamically."""
        async with self._lock:
            if self._session is not None:
                return

            last_error: Exception | None = None
            for _ in range(self.connect_retries):
                try:
                    read_stream, write_stream = await self._stack.enter_async_context(
                        sse_client(self.server_url)
                    )
                    self._session = await self._stack.enter_async_context(
                        ClientSession(read_stream, write_stream)
                    )
                    await self._session.initialize()
                    await self.refresh_tools()
                    return
                except Exception as exc:
                    last_error = exc
                    await asyncio.sleep(self.retry_delay_seconds)

            raise RuntimeError(f"Unable to connect to MCP server at {self.server_url}: {last_error}")

    async def close(self) -> None:
        async with self._lock:
            self._session = None
            self._tools = []
            self._openai_tools = []
            await self._stack.aclose()

    async def refresh_tools(self) -> None:
        """Re-fetch tools from MCP server (tools/list)."""
        if self._session is None:
            raise RuntimeError("MCP session is not connected.")

        result = await self._session.list_tools()
        self._tools = list(result.tools)
        self._openai_tools = [self._tool_to_openai_schema(tool) for tool in self._tools]

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        return list(self._openai_tools)

    async def call_tool(self, name: str, arguments: Dict[str, Any] | None = None) -> str:
        """Execute a tool through MCP tools/call and normalize output to text."""
        if self._session is None:
            raise RuntimeError("MCP session is not connected.")

        result = await self._session.call_tool(name=name, arguments=arguments or {})
        return self._call_result_to_text(result)

    def _tool_to_openai_schema(self, tool: Tool) -> Dict[str, Any]:
        parameters = tool.inputSchema if isinstance(tool.inputSchema, dict) else {"type": "object"}
        if "type" not in parameters:
            parameters = {"type": "object", **parameters}

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": parameters,
            },
        }

    def _call_result_to_text(self, result: CallToolResult) -> str:
        parts: List[str] = []

        for content in result.content:
            if getattr(content, "type", None) == "text":
                parts.append(getattr(content, "text", ""))
            else:
                parts.append(json.dumps(content.model_dump(by_alias=True), default=str))

        if result.structuredContent is not None:
            parts.append(json.dumps(result.structuredContent, default=str))

        if not parts:
            return json.dumps({"ok": not result.isError})

        return "\n".join(part for part in parts if part)
