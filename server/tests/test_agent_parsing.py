from server.services.agent_runner import _normalize_agent_decision, _parse_agent_json


def test_parse_plain_json():
    assert _parse_agent_json('{"action":"final","answer":"ok"}') == {
        "action": "final",
        "answer": "ok",
    }


def test_parse_json_wrapped_in_code_fence():
    raw = '```json\n{"tool_calls":[{"name":"calculator","parameters":{"expression":"1+1"}}]}\n```'
    parsed = _parse_agent_json(raw)
    assert parsed["tool_calls"][0]["name"] == "calculator"


def test_parse_json_embedded_in_prose():
    raw = '好的，我将调用工具。{"action":"final","answer":"42"} 以上。'
    assert _parse_agent_json(raw)["answer"] == "42"


def test_parse_garbage_returns_empty():
    assert _parse_agent_json("这不是 JSON") == {}


def test_normalize_openwebui_style_tool_calls():
    decision = _normalize_agent_decision(
        {"tool_calls": [{"name": "get_current_time", "parameters": {}}]}
    )
    assert decision["action"] == "tool"
    assert decision["tool_calls"][0]["name"] == "get_current_time"


def test_normalize_legacy_action_tool_format():
    decision = _normalize_agent_decision(
        {"action": "tool", "tool": "calculator", "input": {"expression": "2*3"}}
    )
    assert decision["tool_calls"] == [
        {"name": "calculator", "parameters": {"expression": "2*3"}}
    ]


def test_normalize_small_model_action_as_tool_name():
    # Small local models often emit {"action":"calculator","expression":"..."}.
    decision = _normalize_agent_decision({"action": "calculator", "expression": "7*6"})
    assert decision["action"] == "tool"
    assert decision["tool_calls"][0] == {
        "name": "calculator",
        "parameters": {"expression": "7*6"},
    }


def test_normalize_final_passthrough():
    decision = _normalize_agent_decision({"action": "final", "answer": "done"})
    assert decision == {"action": "final", "answer": "done"}
