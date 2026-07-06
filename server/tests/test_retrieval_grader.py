"""检索自纠错（Grader + 有界重检索）的单测。"""
from __future__ import annotations

import pytest

from server.schemas.config import ProviderConfig
from server.services import retrieval_grader
from server.services.retrieval_grader import (
    _parse_grader_json,
    grade_retrieval,
    merge_chunks,
)

CONFIG = ProviderConfig()
CHUNKS = [
    {"chunk_id": "c1", "content": "OA 系统默认端口 8080", "filename": "a.md", "file_id": "f1", "chunk_index": 0, "score": 0.9},
    {"chunk_id": "c2", "content": "请假流程需主管审批", "filename": "a.md", "file_id": "f1", "chunk_index": 1, "score": 0.8},
]


def _chunk(chunk_id: str) -> dict:
    return {"chunk_id": chunk_id, "content": chunk_id, "filename": "x", "file_id": "f", "chunk_index": 0, "score": 0.5}


# ─── _parse_grader_json ──────────────────────────────

def test_parse_plain_json() -> None:
    assert _parse_grader_json('{"sufficient": true}') == {"sufficient": True}


def test_parse_fenced_json() -> None:
    raw = '```json\n{"sufficient": false, "followup_query": "端口配置"}\n```'
    assert _parse_grader_json(raw) == {"sufficient": False, "followup_query": "端口配置"}


def test_parse_json_with_prose() -> None:
    raw = '根据分析，{"sufficient": true} 就是结论'
    assert _parse_grader_json(raw) == {"sufficient": True}


def test_parse_garbage_returns_none() -> None:
    assert _parse_grader_json("完全不是 JSON") is None


# ─── grade_retrieval ──────────────────────────────

@pytest.mark.anyio
async def test_sufficient_keeps_first_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_completion(config, payload):  # noqa: ANN001
        return '{"sufficient": true}'

    monkeypatch.setattr(retrieval_grader, "create_chat_completion_text", fake_completion)
    sufficient, followup = await grade_retrieval(CONFIG, "m", "端口是多少", CHUNKS)
    assert sufficient is True
    assert followup == ""


@pytest.mark.anyio
async def test_insufficient_returns_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_completion(config, payload):  # noqa: ANN001
        return '{"sufficient": false, "followup_query": "OA 系统数据库配置"}'

    monkeypatch.setattr(retrieval_grader, "create_chat_completion_text", fake_completion)
    sufficient, followup = await grade_retrieval(CONFIG, "m", "数据库怎么配", CHUNKS)
    assert sufficient is False
    assert followup == "OA 系统数据库配置"


@pytest.mark.anyio
async def test_malformed_output_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_completion(config, payload):  # noqa: ANN001
        return "我觉得资料不够"

    monkeypatch.setattr(retrieval_grader, "create_chat_completion_text", fake_completion)
    sufficient, _ = await grade_retrieval(CONFIG, "m", "q", CHUNKS)
    assert sufficient is True


@pytest.mark.anyio
async def test_llm_error_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_completion(config, payload):  # noqa: ANN001
        raise RuntimeError("provider down")

    monkeypatch.setattr(retrieval_grader, "create_chat_completion_text", fake_completion)
    sufficient, _ = await grade_retrieval(CONFIG, "m", "q", CHUNKS)
    assert sufficient is True


@pytest.mark.anyio
async def test_insufficient_without_followup_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_completion(config, payload):  # noqa: ANN001
        return '{"sufficient": false, "followup_query": ""}'

    monkeypatch.setattr(retrieval_grader, "create_chat_completion_text", fake_completion)
    sufficient, _ = await grade_retrieval(CONFIG, "m", "q", CHUNKS)
    assert sufficient is True


@pytest.mark.anyio
async def test_empty_chunks_skip_grading() -> None:
    sufficient, _ = await grade_retrieval(CONFIG, "m", "q", [])
    assert sufficient is True


# ─── merge_chunks ──────────────────────────────

def test_merge_keeps_first_pass_and_appends_new() -> None:
    """首轮结果不能被二轮挤掉（Grader 可能误判），二轮去重后追加。"""
    first = [_chunk("a"), _chunk("b"), _chunk("c")]
    second = [_chunk("b"), _chunk("d")]
    merged = merge_chunks(first, second, top_k=4)
    assert [c["chunk_id"] for c in merged] == ["a", "b", "c", "d"]


def test_merge_respects_enlarged_budget() -> None:
    """预算为 top_k + max(2, top_k//2)，超出部分截断。"""
    first = [_chunk("a"), _chunk("b"), _chunk("c"), _chunk("d")]
    second = [_chunk("e"), _chunk("f"), _chunk("g")]
    merged = merge_chunks(first, second, top_k=4)  # budget = 6
    assert [c["chunk_id"] for c in merged] == ["a", "b", "c", "d", "e", "f"]
