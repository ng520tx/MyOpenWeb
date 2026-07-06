"""联网搜索真实冒烟：直连 DuckDuckGo 搜一条，看返回结构。

    ./.venv/bin/python -m server.eval.web_search_smoke
"""
from __future__ import annotations

import asyncio

from server.services.web_search import search_web


async def main() -> None:
    result = await search_web("Ollama 最新版本 release", max_results=3)
    if result.get("error"):
        print(f"降级路径生效：{result['error']}")
        return
    for row in result["results"]:
        print(f"- {row['title']}\n  {row['url']}\n  {row['snippet'][:80]}")
    print("web search smoke OK")


if __name__ == "__main__":
    asyncio.run(main())
