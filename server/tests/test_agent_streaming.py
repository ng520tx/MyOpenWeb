"""Agent event streaming: the tool loop should surface thinking / tool_call /
tool_result progress events before the terminal result, and the SSE adapter
should wrap them in OpenAI-compatible frames."""
from __future__ import annotations

import json

import pytest

import server.services.agent_runner as agent_runner
from server.schemas.config import ProviderConfig


def _config() -> ProviderConfig:
    return ProviderConfig()


def _fake_completion_factory(responses: list[str]):
    """Return an async stub that plays back canned model responses in order."""
    calls = {"count": 0}

    async def fake(config, payload):
        index = min(calls["count"], len(responses) - 1)
        calls["count"] += 1
        return responses[index]

    return fake


@pytest.mark.anyio
async def test_run_agent_events_yields_progress_then_result(monkeypatch):
    monkeypatch.setattr(
        agent_runner,
        "create_chat_completion_text",
        _fake_completion_factory(
            [
                '{"tool_calls":[{"name":"calculator","parameters":{"expression":"6*7"}}]}',
                '{"action":"final","answer":"结果是 42"}',
            ]
        ),
    )

    events: list[dict] = []
    result: dict | None = None
    async for kind, data in agent_runner.run_agent_events(
        _config(), {"model": "test", "messages": [{"role": "user", "content": "算一下 6*7"}]}
    ):
        if kind == "event":
            events.append(data)
        else:
            result = data

    types = [event["type"] for event in events]
    assert types == ["thinking", "tool_call", "tool_result", "thinking"]
    assert events[1]["name"] == "calculator"
    assert events[2]["ok"] is True
    assert "42" in events[2]["summary"]

    assert result is not None
    assert result["answer"] == "结果是 42"
    assert result["agent"]["toolCalls"][0]["name"] == "calculator"


@pytest.mark.anyio
async def test_stream_agent_sse_frames(monkeypatch):
    monkeypatch.setattr(
        agent_runner,
        "create_chat_completion_text",
        _fake_completion_factory(['{"action":"final","answer":"直接回答"}']),
    )

    frames: list[bytes] = []
    async for chunk in agent_runner._stream_agent_sse(
        _config(), {"model": "test", "messages": [{"role": "user", "content": "你好"}]}
    ):
        frames.append(chunk)

    assert frames[-1] == b"data: [DONE]\n\n"

    parsed = [
        json.loads(frame.decode("utf-8").removeprefix("data: "))
        for frame in frames[:-1]
    ]
    # First frame: thinking progress event with an empty delta (older clients ignore it).
    assert parsed[0]["agent_event"]["type"] == "thinking"
    assert parsed[0]["choices"][0]["delta"] == {}
    # Then the final answer content, then the stop frame carrying agent + sources.
    assert parsed[-2]["choices"][0]["delta"]["content"] == "直接回答"
    assert parsed[-1]["choices"][0]["finish_reason"] == "stop"
    assert "agent" in parsed[-1] and "sources" in parsed[-1]
