"""MCP server 注册与工具包装的单测（不拉起 stdio 进程）。"""
from __future__ import annotations

import pytest

from server.mcp_server.main import (
    _resolve_knowledge_id,
    analyze_log,
    mcp,
    summarize_git_diff,
)
from server.repositories.knowledge import create_knowledge, delete_knowledge

EXPECTED_TOOLS = {
    "list_knowledge_bases",
    "search_knowledge",
    "analyze_log",
    "summarize_git_diff",
    "summarize_ticket",
    "generate_test_cases",
}


@pytest.mark.anyio
async def test_all_tools_registered() -> None:
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert names >= EXPECTED_TOOLS


def test_resolve_knowledge_by_name_and_id() -> None:
    knowledge = create_knowledge("mcp-测试库", "for mcp test")
    try:
        assert _resolve_knowledge_id("mcp-测试库") == knowledge.id
        assert _resolve_knowledge_id(knowledge.id) == knowledge.id
        assert _resolve_knowledge_id("不存在的库") is None
        assert _resolve_knowledge_id("  ") is None
    finally:
        delete_knowledge(knowledge.id)


def test_analyze_log_wrapper_returns_structured_result() -> None:
    result = analyze_log("2026-01-01 ERROR db timeout\n2026-01-01 INFO ok")
    assert result["total_lines"] == 2
    assert result["level_counts"]["ERROR"] == 1


def test_summarize_git_diff_wrapper() -> None:
    diff = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n+print(1)\n"
    result = summarize_git_diff(diff)
    assert result["files_changed"] == 1
