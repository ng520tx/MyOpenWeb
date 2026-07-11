"""The agent tool loop ceiling is configurable (agent_max_rounds, clamped 1-10)."""
from __future__ import annotations

import pytest

import server.services.agent_runner as agent_runner
from server.repositories.configs import get_provider_config, update_provider_config
from server.schemas.config import ProviderConfig


def test_agent_max_rounds_is_clamped_on_persist():
    base = get_provider_config()
    try:
        stored = update_provider_config(base.model_copy(update={"agent_max_rounds": 99}))
        assert stored.agent_max_rounds == 10
        assert get_provider_config().agent_max_rounds == 10

        stored = update_provider_config(base.model_copy(update={"agent_max_rounds": 0}))
        assert stored.agent_max_rounds == 1

        stored = update_provider_config(base.model_copy(update={"agent_max_rounds": 5}))
        assert stored.agent_max_rounds == 5
    finally:
        update_provider_config(base)


@pytest.mark.anyio
async def test_loop_stops_at_configured_ceiling(monkeypatch):
    calls = {"count": 0}

    async def always_calls_tool(config, payload):
        calls["count"] += 1
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": '{"tool_calls":[{"name":"get_current_time","parameters":{}}]}',
                    }
                }
            ]
        }

    monkeypatch.setattr(agent_runner, "create_chat_completion_full", always_calls_tool)

    result = await agent_runner.run_agent(
        ProviderConfig(agent_max_rounds=1),
        {"model": "test", "messages": [{"role": "user", "content": "现在几点"}]},
    )

    assert calls["count"] == 1
    assert "最大步数" in result["answer"]
    # The single permitted round still executed its tool before the cutoff.
    assert result["agent"]["toolCalls"][0]["name"] == "get_current_time"
