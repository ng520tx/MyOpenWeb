"""联网搜索工具：结果结构、参数钳制与永不抛异常的降级行为。"""
from __future__ import annotations

import pytest

from server.services import web_search
from server.services.web_search import search_web, web_search_tool


@pytest.mark.anyio
async def test_results_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_ddgs(query: str, max_results: int) -> list[dict[str, str]]:
        assert query == "ollama 最新版本"
        assert max_results == 3
        return [
            {"title": "Ollama releases", "url": "https://example.com", "snippet": "v0.30 发布"},
        ]

    monkeypatch.setattr(web_search, "_search_ddgs", fake_ddgs)
    result = await search_web("ollama 最新版本", max_results=3)
    assert result == {
        "results": [
            {"title": "Ollama releases", "url": "https://example.com", "snippet": "v0.30 发布"}
        ]
    }


@pytest.mark.anyio
async def test_empty_query_short_circuits() -> None:
    result = await search_web("   ")
    assert result["error"]
    assert result["results"] == []


@pytest.mark.anyio
async def test_max_results_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int] = {}

    def fake_ddgs(query: str, max_results: int) -> list[dict[str, str]]:
        captured["max_results"] = max_results
        return []

    monkeypatch.setattr(web_search, "_search_ddgs", fake_ddgs)
    result = await search_web("q", max_results=99)
    assert captured["max_results"] == 10
    assert "note" in result  # 空结果给模型明确提示


@pytest.mark.anyio
async def test_provider_error_degrades(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_ddgs(query: str, max_results: int) -> list[dict[str, str]]:
        raise ConnectionError("network unreachable")

    monkeypatch.setattr(web_search, "_search_ddgs", fake_ddgs)
    result = await search_web("q")
    assert "联网搜索失败" in result["error"]
    assert result["results"] == []


@pytest.mark.anyio
async def test_unknown_provider_degrades() -> None:
    result = await search_web("q", provider="bocha")
    assert "未知搜索 provider" in result["error"]


def test_tool_spec_shape() -> None:
    spec = web_search_tool()
    assert spec["name"] == "web_search"
    assert "query" in spec["input_schema"]["properties"]
    assert spec["input_schema"]["required"] == ["query"]
