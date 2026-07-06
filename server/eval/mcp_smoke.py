"""MCP server 端到端冒烟：以 stdio 拉起 server 子进程，走真实 MCP 协议调用工具。

用法（WSL venv）：
    ./.venv/bin/python -m server.eval.mcp_smoke
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = StdioServerParameters(
    command=sys.executable,
    args=["-m", "server.mcp_server.main"],
)


def _json_blocks(result) -> list:
    """FastMCP 对 list 返回值会拆成多个 TextContent block，逐个解析。"""
    return [
        json.loads(block.text)
        for block in result.content
        if getattr(block, "text", None)
    ]


def _first_json(result):
    blocks = _json_blocks(result)
    return blocks[0] if blocks else None


async def main() -> None:
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            print(f"[1] list_tools -> {names}")

            result = await session.call_tool(
                "analyze_log",
                {"log": "2026-01-01 ERROR db timeout\n2026-01-01 WARN slow query\n2026-01-01 INFO ok"},
            )
            payload = _first_json(result)
            print(f"[2] analyze_log -> level_counts={payload.get('level_counts')}")

            result = await session.call_tool("list_knowledge_bases", {})
            bases = _json_blocks(result)
            print(f"[3] list_knowledge_bases -> {[b['name'] for b in bases]}")

            if bases:
                name = bases[0]["name"]
                result = await session.call_tool(
                    "search_knowledge", {"knowledge": name, "query": "请假流程", "top_k": 2}
                )
                data = _first_json(result)
                hits = data.get("results", [])
                print(
                    f"[4] search_knowledge('{name}') -> {len(hits)} hits; "
                    f"top={hits[0]['filename'] if hits else 'N/A'}"
                )
            else:
                print("[4] search_knowledge skipped (no knowledge bases)")

    print("MCP smoke OK")


if __name__ == "__main__":
    asyncio.run(main())
