"""LLM 标题生成与追问建议：输出清洗与失败静默。"""
from __future__ import annotations

import pytest

from server.schemas.config import ProviderConfig
from server.services import llm_tasks
from server.services.llm_tasks import (
    _parse_follow_ups,
    generate_follow_ups,
    generate_title,
)

CONFIG = ProviderConfig()


def _fake_completion(reply: str):
    async def fake(config, payload):  # noqa: ANN001
        return reply

    return fake


# ─── generate_title ──────────────────────────────

@pytest.mark.anyio
async def test_title_is_cleaned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_tasks, "create_chat_completion_text", _fake_completion('"OA 系统请假流程。"\n多余的行')
    )
    title = await generate_title(CONFIG, "m", "怎么请假？")
    assert title == "OA 系统请假流程"


@pytest.mark.anyio
async def test_title_truncated_to_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_tasks, "create_chat_completion_text", _fake_completion("这是一个远远超过二十个字符长度限制的超长对话标题示例文本")
    )
    title = await generate_title(CONFIG, "m", "q")
    assert title is not None
    assert len(title) <= 20


@pytest.mark.anyio
async def test_title_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(config, payload):  # noqa: ANN001
        raise RuntimeError("provider down")

    monkeypatch.setattr(llm_tasks, "create_chat_completion_text", fake)
    assert await generate_title(CONFIG, "m", "q") is None


@pytest.mark.anyio
async def test_empty_title_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_tasks, "create_chat_completion_text", _fake_completion('""'))
    assert await generate_title(CONFIG, "m", "q") is None


# ─── follow-ups ──────────────────────────────

def test_parse_plain_array() -> None:
    assert _parse_follow_ups('["a", "b", "c"]') == ["a", "b", "c"]


def test_parse_fenced_array_clipped_to_three() -> None:
    raw = '```json\n["一", "二", "三", "四"]\n```'
    assert _parse_follow_ups(raw) == ["一", "二", "三"]


def test_parse_array_embedded_in_prose() -> None:
    assert _parse_follow_ups('建议如下：["a","b"] 供参考') == ["a", "b"]


def test_parse_garbage_returns_empty() -> None:
    assert _parse_follow_ups("完全不是数组") == []
    assert _parse_follow_ups('{"not": "array"}') == []


def test_parse_strips_numbering_prefixes() -> None:
    raw = '["追问一：默认令牌是多少？", "2. 限流可以调吗？", "问题：怎么恢复？"]'
    assert _parse_follow_ups(raw) == ["默认令牌是多少？", "限流可以调吗？", "怎么恢复？"]


@pytest.mark.anyio
async def test_follow_ups_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_tasks, "create_chat_completion_text", _fake_completion('["端口是多少？","怎么重启？","日志在哪？"]')
    )
    follow_ups = await generate_follow_ups(
        CONFIG, "m", [{"role": "user", "content": "介绍下系统"}, {"role": "assistant", "content": "..."}]
    )
    assert follow_ups == ["端口是多少？", "怎么重启？", "日志在哪？"]


@pytest.mark.anyio
async def test_follow_ups_failure_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(config, payload):  # noqa: ANN001
        raise RuntimeError("timeout")

    monkeypatch.setattr(llm_tasks, "create_chat_completion_text", fake)
    assert await generate_follow_ups(CONFIG, "m", [{"role": "user", "content": "q"}]) == []


@pytest.mark.anyio
async def test_follow_ups_empty_messages_skip_llm() -> None:
    assert await generate_follow_ups(CONFIG, "m", []) == []
