"""Web search tool for the agent, with pluggable providers and graceful degradation.

- 默认 provider `ddgs`（DuckDuckGo，免 key、免配置），依赖很轻
- Provider 以函数分发预留扩展位（bocha / serper 等企业可用源只需加一个分支 +
  对应的 key 配置），结构参考 open-webui `retrieval/web/` 但极简化
- 联网搜索永不抛异常：任何失败（依赖缺失/超时/网络不可达）都返回带 error
  字段的结构化结果，模型能据此明确告诉用户"联网搜索暂不可用"，Agent 循环不中断
- 只在 Agent 模式作为工具由模型自主选用；普通 RAG 路径的拒答逻辑不受影响
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

WEB_SEARCH_TOOL_NAME = "web_search"

DEFAULT_MAX_RESULTS = 5
SEARCH_TIMEOUT_SECONDS = 12
MAX_SNIPPET_CHARS = 300


def web_search_tool() -> dict[str, Any]:
    return {
        "name": WEB_SEARCH_TOOL_NAME,
        "description": (
            "联网搜索公开网页信息，返回标题、链接与摘要列表。"
            "当问题涉及时效性信息（新闻、版本发布、价格）或知识库/已有资料无法回答时使用；"
            "回答时把引用的链接列出来。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词，尽量具体"},
                "max_results": {"type": "integer", "description": f"返回条数，默认 {DEFAULT_MAX_RESULTS}"},
            },
            "required": ["query"],
        },
    }


def _search_ddgs(query: str, max_results: int) -> list[dict[str, str]]:
    """DuckDuckGo via the ddgs package (sync; called through a worker thread)."""
    from ddgs import DDGS  # 延迟导入：未安装依赖时走降级分支而不是启动即失败

    results = []
    with DDGS(timeout=SEARCH_TIMEOUT_SECONDS) as client:
        for row in client.text(query, max_results=max_results):
            results.append(
                {
                    "title": str(row.get("title") or "")[:200],
                    "url": str(row.get("href") or ""),
                    "snippet": str(row.get("body") or "")[:MAX_SNIPPET_CHARS],
                }
            )
    return results


async def search_web(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    provider: str = "ddgs",
) -> dict[str, Any]:
    """Run a web search. Never raises: failures come back as {"error": ...}."""
    query = (query or "").strip()
    if not query:
        return {"error": "搜索关键词为空", "results": []}

    max_results = max(1, min(int(max_results or DEFAULT_MAX_RESULTS), 10))

    try:
        if provider == "ddgs":
            results = await asyncio.wait_for(
                asyncio.to_thread(_search_ddgs, query, max_results),
                timeout=SEARCH_TIMEOUT_SECONDS + 3,
            )
        else:
            return {"error": f"未知搜索 provider: {provider}", "results": []}
    except ImportError:
        return {
            "error": "联网搜索依赖未安装（pip install ddgs），请告知用户联网搜索暂不可用",
            "results": [],
        }
    except asyncio.TimeoutError:
        return {"error": "联网搜索超时，请告知用户稍后再试或改用知识库", "results": []}
    except Exception as exc:  # noqa: BLE001 - tool must never break the agent loop
        logger.warning("web search failed: %s", exc)
        return {"error": f"联网搜索失败：{exc}", "results": []}

    if not results:
        return {"results": [], "note": "没有搜到相关结果，可以换个关键词再试"}
    return {"results": results}
