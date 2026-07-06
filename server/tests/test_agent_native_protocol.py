"""Native function-calling protocol: tool specs travel via the provider tools
API, responses come back as structured tool_calls, and tool results feed back
as role=tool messages."""
from __future__ import annotations

import pytest

import server.services.agent_runner as agent_runner
from server.schemas.config import ProviderConfig


def _native_config() -> ProviderConfig:
    return ProviderConfig(agent_tool_protocol="native")


def test_to_openai_tools_schema():
    tools = agent_runner._to_openai_tools(
        [{"name": "calculator", "description": "算术", "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}]
    )
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "calculator"
    assert tools[0]["function"]["parameters"]["required"] == ["expression"]


def test_decision_from_native_with_dict_arguments():
    # Ollama's native API returns arguments as a dict.
    decision = agent_runner._decision_from_native(
        {"content": "", "tool_calls": [{"function": {"name": "calculator", "arguments": {"expression": "6*7"}}}]}
    )
    assert decision == {
        "action": "tool",
        "tool_calls": [{"name": "calculator", "parameters": {"expression": "6*7"}}],
    }


def test_decision_from_native_with_string_arguments():
    # OpenAI-compatible endpoints return arguments as a JSON string.
    decision = agent_runner._decision_from_native(
        {"content": None, "tool_calls": [{"id": "call_1", "function": {"name": "get_current_time", "arguments": "{}"}}]}
    )
    assert decision["tool_calls"] == [{"name": "get_current_time", "parameters": {}}]


def test_decision_from_native_without_tool_calls_is_final():
    decision = agent_runner._decision_from_native({"content": "直接回答", "tool_calls": []})
    assert decision == {"action": "final", "answer": "直接回答"}


@pytest.mark.anyio
async def test_native_loop_executes_tool_and_feeds_back_tool_message(monkeypatch):
    responses = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_abc", "function": {"name": "calculator", "arguments": {"expression": "6*7"}}}
            ],
        },
        {"role": "assistant", "content": "答案是 42"},
    ]
    seen_payloads: list[dict] = []

    async def fake_message(config, payload):
        seen_payloads.append(payload)
        return responses[min(len(seen_payloads) - 1, len(responses) - 1)]

    monkeypatch.setattr(agent_runner, "create_chat_completion_message", fake_message)

    result = None
    events = []
    async for kind, data in agent_runner.run_agent_events(
        _native_config(), {"model": "test", "messages": [{"role": "user", "content": "算 6*7"}]}
    ):
        if kind == "result":
            result = data
        else:
            events.append(data)

    assert result is not None
    assert result["answer"] == "答案是 42"
    assert [event["type"] for event in events] == ["thinking", "tool_call", "tool_result", "thinking"]

    # Round 1 must carry tool specs; round 2 must replay the tool exchange.
    assert seen_payloads[0]["tools"][0]["function"]["name"] in agent_runner.TOOL_NAMES
    second_round_messages = seen_payloads[1]["messages"]
    assert second_round_messages[-2]["role"] == "assistant"
    assert second_round_messages[-2]["tool_calls"][0]["function"]["name"] == "calculator"
    assert second_round_messages[-1]["role"] == "tool"
    assert second_round_messages[-1]["tool_call_id"] == "call_abc"
    assert "42" in second_round_messages[-1]["content"]
