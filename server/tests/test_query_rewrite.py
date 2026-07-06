"""Multi-turn query rewriting: pronoun-laden follow-ups should be expanded via
the chat model, and every failure path must fall back to the raw query."""
from __future__ import annotations

import pytest

import server.services.query_rewrite as qr
from server.schemas.config import ProviderConfig


SINGLE_TURN = [{"role": "user", "content": "FastAPI 服务的默认端口是多少？"}]

MULTI_TURN = [
    {"role": "user", "content": "介绍一下 MyOpenWeb 的后端服务"},
    {"role": "assistant", "content": "MyOpenWeb 后端是 FastAPI 实现的本地服务……"},
    {"role": "user", "content": "它的默认端口是多少？"},
]


def _config() -> ProviderConfig:
    return ProviderConfig()


def test_needs_rewrite_only_for_multi_turn():
    assert qr.needs_rewrite(SINGLE_TURN) is False
    assert qr.needs_rewrite(MULTI_TURN) is True


@pytest.mark.anyio
async def test_rewrite_uses_model_output(monkeypatch):
    captured: dict = {}

    async def fake(config, payload):
        captured["payload"] = payload
        return "MyOpenWeb FastAPI 后端服务的默认端口"

    monkeypatch.setattr(qr, "create_chat_completion_text", fake)

    result = await qr.rewrite_query(
        _config(), {"model": "test", "messages": MULTI_TURN}, "它的默认端口是多少？"
    )
    assert result == "MyOpenWeb FastAPI 后端服务的默认端口"
    # The rewrite prompt should carry conversation history and the raw question.
    prompt = captured["payload"]["messages"][0]["content"]
    assert "介绍一下 MyOpenWeb" in prompt
    assert "它的默认端口是多少" in prompt


@pytest.mark.anyio
async def test_rewrite_falls_back_on_model_failure(monkeypatch):
    async def fake(config, payload):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(qr, "create_chat_completion_text", fake)

    result = await qr.rewrite_query(
        _config(), {"model": "test", "messages": MULTI_TURN}, "它的默认端口是多少？"
    )
    assert result == "它的默认端口是多少？"


@pytest.mark.anyio
async def test_rewrite_falls_back_on_garbage_output(monkeypatch):
    async def fake(config, payload):
        return "好的，" + "很长的解释" * 100

    monkeypatch.setattr(qr, "create_chat_completion_text", fake)

    result = await qr.rewrite_query(
        _config(), {"model": "test", "messages": MULTI_TURN}, "它的默认端口是多少？"
    )
    assert result == "它的默认端口是多少？"


@pytest.mark.anyio
async def test_single_turn_skips_model_call(monkeypatch):
    calls = {"count": 0}

    async def fake(config, payload):
        calls["count"] += 1
        return "should not happen"

    monkeypatch.setattr(qr, "create_chat_completion_text", fake)

    result = await qr.rewrite_query(
        _config(), {"model": "test", "messages": SINGLE_TURN}, "FastAPI 服务的默认端口是多少？"
    )
    assert result == "FastAPI 服务的默认端口是多少？"
    assert calls["count"] == 0
