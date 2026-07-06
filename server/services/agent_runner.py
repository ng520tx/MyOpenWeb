from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

from server.repositories.agent_runs import add_agent_step, create_agent_run, finish_agent_run
from server.repositories.memories import list_enabled_memories
from server.schemas.config import ProviderConfig
from server.services.agent_tools import (
    KNOWLEDGE_TOOL_NAME,
    ToolError,
    knowledge_search_tool,
    list_tools,
    run_tool,
)
from server.services.providers import create_chat_completion_text
from server.services.rag import query_knowledge, serialize_sources


AGENT_INSTRUCTION = """你是 MyOpenWeb 的 Agent v1。
你可以使用后端提供的安全工具，但不能编造工具结果。

可用工具：
{tools}

你每次只能输出一个 JSON 对象，不能输出 Markdown，不能输出代码块。

如果需要调用工具，输出 Open WebUI 风格的 tool_calls 数组：
{{"tool_calls":[{{"name":"工具名","parameters":{{...}}}}]}}

示例：
{{"tool_calls":[{{"name":"get_current_time","parameters":{{}}}}]}}
{{"tool_calls":[{{"name":"calculator","parameters":{{"expression":"(12 + 8) * 3 / 2"}}}}]}}

如果可以最终回答，输出：
{{"action":"final","answer":"最终回答内容"}}

注意：
- 如果调用工具，必须使用 tool_calls 数组
- 工具执行结果会由后端提供，你不能自己猜测工具结果
"""


# Injected only when the user selected a knowledge base, so out-of-scope
# questions get a clean refusal instead of a generic, hallucinated answer.
KNOWLEDGE_REFUSAL_GUIDANCE = """本次对话已选定企业知识库，你的回答必须以知识库为准：
- 涉及事实/资料性的问题，必须先调用 search_knowledge 检索。
- 如果 search_knowledge 返回为空，或返回内容与用户问题无关，必须直接回答“知识库中没有找到相关信息”，不要用通用知识编造，也不要展开无关内容。
- 命中资料时，依据资料作答，并在引用具体内容时用 [序号] 标注来源。"""


TOOL_NAMES = {tool["name"] for tool in list_tools()} | {KNOWLEDGE_TOOL_NAME}


async def create_agent_completion(config: ProviderConfig, payload: dict):
    if payload.get("stream", True):
        return StreamingResponse(
            _stream_agent_sse(config, payload),
            media_type="text/event-stream",
        )

    result = await run_agent(config, payload)
    return {
        "id": "agentcmpl-myopenweb",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["answer"]},
                "finish_reason": "stop",
            }
        ],
        "agent": result["agent"],
        "sources": result["sources"],
    }


async def run_agent(config: ProviderConfig, payload: dict) -> dict[str, Any]:
    """Non-streaming entry: drain the event generator and return the final result."""
    result: dict[str, Any] | None = None
    async for kind, data in run_agent_events(config, payload):
        if kind == "result":
            result = data
    assert result is not None  # the generator always terminates with a result
    return result


async def run_agent_events(
    config: ProviderConfig, payload: dict
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Run the tool loop, yielding ("event", {...}) progress items along the way
    and exactly one terminal ("result", {...}) item."""
    messages = list(payload.get("messages", []))
    steps: list[dict[str, Any]] = []
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    user_input = _get_last_user_text(messages)
    run_id = create_agent_run(
        conversation_id=metadata.get("conversation_id"),
        message_id=metadata.get("assistant_message_id"),
        user_message_id=metadata.get("user_message_id"),
        model=str(payload.get("model", "")),
        user_input=user_input,
    )
    step_index = 0
    base_system_prompt = payload.get("system_prompt") or ""
    memory_context = _build_memory_context()

    knowledge_id = payload.get("knowledge_id")
    available_tools = list_tools()
    if knowledge_id:
        available_tools = [*available_tools, knowledge_search_tool()]

    agent_system_prompt = AGENT_INSTRUCTION.format(
        tools=json.dumps(available_tools, ensure_ascii=False, indent=2)
    )
    knowledge_guidance = KNOWLEDGE_REFUSAL_GUIDANCE if knowledge_id else ""
    system_prompt = "\n\n".join(
        part
        for part in [base_system_prompt, memory_context, agent_system_prompt, knowledge_guidance]
        if part
    )
    collected_chunks: list[dict[str, Any]] = []

    for round_index in range(3):
        yield ("event", {"type": "thinking", "round": round_index + 1})
        raw = await create_chat_completion_text(
            config,
            {
                **payload,
                "messages": messages,
                "system_prompt": system_prompt,
                "stream": False,
            },
        )
        decision = _normalize_agent_decision(_parse_agent_json(raw))
        add_agent_step(
            run_id=run_id,
            step_index=step_index,
            step_type="model_decision",
            input_data={"messages_count": len(messages)},
            output_data={"raw": raw, "decision": decision},
        )
        step_index += 1

        if decision.get("action") == "final":
            answer = str(decision.get("answer", "")).strip()
            final_answer = answer or "Agent 没有生成有效回答。"
            add_agent_step(
                run_id=run_id,
                step_index=step_index,
                step_type="final",
                output_data={"answer": final_answer},
            )
            finish_agent_run(run_id, final_answer)
            yield ("result", _agent_result(run_id, final_answer, steps, collected_chunks))
            return

        tool_calls = decision.get("tool_calls") if isinstance(decision.get("tool_calls"), list) else []

        if not tool_calls:
            final_answer = raw.strip() or "Agent 返回了无法解析的内容。"
            add_agent_step(
                run_id=run_id,
                step_index=step_index,
                step_type="final",
                output_data={"answer": final_answer},
            )
            finish_agent_run(run_id, final_answer)
            yield ("result", _agent_result(run_id, final_answer, steps, collected_chunks))
            return

        tool_results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            tool_name = str(tool_call.get("name", "")).strip()
            tool_input = tool_call.get("parameters") if isinstance(tool_call.get("parameters"), dict) else {}
            yield ("event", {"type": "tool_call", "name": tool_name, "parameters": tool_input})
            add_agent_step(
                run_id=run_id,
                step_index=step_index,
                step_type="tool_call",
                name=tool_name,
                input_data=tool_input,
            )
            step_index += 1
            step: dict[str, Any] = {
                "tool": tool_name,
                "input": tool_input,
            }

            try:
                if tool_name == KNOWLEDGE_TOOL_NAME:
                    output = await _run_knowledge_search(
                        config, knowledge_id, tool_input, user_input, collected_chunks
                    )
                else:
                    output = run_tool(tool_name, tool_input)
                step["ok"] = True
                step["output"] = output
            except (ToolError, ZeroDivisionError, OverflowError) as exc:
                output = {"error": str(exc)}
                step["ok"] = False
                step["error"] = str(exc)
            add_agent_step(
                run_id=run_id,
                step_index=step_index,
                step_type="tool_result",
                name=tool_name,
                input_data=tool_input,
                output_data=output,
                ok=bool(step["ok"]),
                error=step.get("error"),
            )
            step_index += 1

            steps.append(step)
            tool_results.append({"name": tool_name, "parameters": tool_input, "result": output})
            yield (
                "event",
                {
                    "type": "tool_result",
                    "name": tool_name,
                    "ok": bool(step["ok"]),
                    "summary": _summarize_tool_output(output),
                    "error": step.get("error"),
                },
            )

        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": (
                "工具执行结果如下：\n"
                f"{json.dumps(tool_results, ensure_ascii=False)}\n"
                "请基于工具结果继续。仍然只能输出一个 JSON 对象。"
            ),
        })

    final_answer = "Agent 工具调用超过最大步数，已停止。请把问题拆小一点再试。"
    add_agent_step(
        run_id=run_id,
        step_index=step_index,
        step_type="final",
        output_data={"answer": final_answer},
        ok=False,
        error="max_steps_exceeded",
    )
    finish_agent_run(run_id, final_answer)
    yield ("result", _agent_result(run_id, final_answer, steps, collected_chunks))


def _agent_result(
    run_id: str,
    answer: str,
    steps: list[dict[str, Any]],
    chunks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "answer": answer,
        "steps": steps,
        "sources": serialize_sources(_dedupe_chunks(chunks or [])),
        "agent": {
            "runId": run_id,
            "toolCalls": [
                {
                    "name": step.get("tool", ""),
                    "input": step.get("input", {}),
                    "output": step.get("output"),
                    "ok": bool(step.get("ok", False)),
                    "error": step.get("error"),
                }
                for step in steps
            ],
        },
    }


def _dedupe_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for chunk in chunks:
        key = chunk.get("chunk_id")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        result.append(chunk)
    return result


async def _run_knowledge_search(
    config: ProviderConfig,
    knowledge_id: str | None,
    tool_input: dict[str, Any],
    user_input: str,
    collected_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    if not knowledge_id:
        return {"error": "未选择知识库，无法检索"}
    query = str(tool_input.get("query") or "").strip() or user_input
    try:
        top_k = int(tool_input.get("top_k") or 4)
    except (TypeError, ValueError):
        top_k = 4
    chunks = await query_knowledge(config, config.embedding_model, knowledge_id, query, top_k)
    collected_chunks.extend(chunks)
    if not chunks:
        return {"results": [], "note": "知识库中没有找到相关内容"}
    return {
        "results": [
            {
                "filename": chunk["filename"],
                "score": round(chunk["score"], 4),
                "content": chunk["content"],
            }
            for chunk in chunks
        ]
    }


def _get_last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(str(part.get("text", "")) for part in content if part.get("type") == "text")
    return ""


def _build_memory_context() -> str:
    memories = list_enabled_memories()
    if not memories:
        return ""

    lines = [
        "以下是用户手动保存的长期记忆。只有在相关时使用，不要逐字背诵：",
    ]
    for memory in memories[:20]:
        lines.append(f"- [{memory.category}] {memory.content}")
    return "\n".join(lines)


def _parse_agent_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


def _normalize_agent_decision(decision: dict[str, Any]) -> dict[str, Any]:
    action = str(decision.get("action", "")).strip()

    if isinstance(decision.get("tool_calls"), list):
        return {
            "action": "tool",
            "tool_calls": [_normalize_tool_call(call) for call in decision["tool_calls"] if isinstance(call, dict)],
        }

    if action == "final":
        return decision

    if action == "tool":
        tool_name = str(decision.get("tool", "")).strip()
        tool_input = decision.get("input") if isinstance(decision.get("input"), dict) else {}
        return {
            "action": "tool",
            "tool_calls": [{"name": tool_name, "parameters": tool_input}],
        }

    # Some small local models output {"action":"calculator","expression":"..."}
    # instead of the stricter {"tool_calls":[{"name":"calculator","parameters":{...}}]}.
    # Treat that as a tool request instead of leaking the JSON to the user.
    if action in TOOL_NAMES:
        tool_input = dict(decision)
        tool_input.pop("action", None)
        tool_input.pop("tool", None)
        return {
            "action": "tool",
            "tool_calls": [{"name": action, "parameters": tool_input}],
        }

    tool_name = str(decision.get("tool", "")).strip()
    if tool_name in TOOL_NAMES:
        tool_input = decision.get("input") if isinstance(decision.get("input"), dict) else {}
        return {
            "action": "tool",
            "tool_calls": [{"name": tool_name, "parameters": tool_input}],
        }

    return decision


def _normalize_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    name = str(tool_call.get("name") or tool_call.get("tool") or "").strip()
    parameters = tool_call.get("parameters")
    if not isinstance(parameters, dict):
        parameters = tool_call.get("input")
    if not isinstance(parameters, dict):
        parameters = {}
    return {"name": name, "parameters": parameters}


def _summarize_tool_output(output: Any, limit: int = 160) -> str:
    """Compact one-line preview for the streamed timeline; full output stays in agent_steps."""
    try:
        text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(output)
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _sse_frame(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


async def _stream_agent_sse(config: ProviderConfig, payload: dict) -> AsyncIterator[bytes]:
    """Stream agent progress as OpenAI-compatible SSE. Intermediate steps ride in
    an ``agent_event`` field with an empty delta so older clients ignore them."""
    result: dict[str, Any] | None = None
    async for kind, data in run_agent_events(config, payload):
        if kind == "event":
            yield _sse_frame(
                {
                    "agent_event": data,
                    "choices": [{"delta": {}, "finish_reason": None}],
                }
            )
        else:
            result = data

    assert result is not None
    yield _sse_frame(
        {"choices": [{"delta": {"content": result["answer"]}, "finish_reason": None}]}
    )
    yield _sse_frame(
        {
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "agent": result["agent"],
            "sources": result["sources"],
        }
    )
    yield b"data: [DONE]\n\n"
