"""Retrieval failures must degrade, not take the chat or the agent run down.

When the embedding service / vector store is unreachable, the chat endpoint
falls back to a plain (non-RAG) answer and flags it via ``retrieval_warning``;
the agent's search_knowledge tool returns a structured error the model can
relay instead of aborting the whole run.
"""
from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

import server.routers.chat_proxy as chat_proxy
import server.services.agent_runner as agent_runner
from server.schemas.chat import ChatCompletionRequest
from server.schemas.config import ProviderConfig


def _request(stream: bool) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model="test",
        messages=[{"role": "user", "content": "问知识库"}],
        stream=stream,
        knowledge_id="kb-1",
    )


@pytest.mark.anyio
async def test_chat_degrades_to_plain_answer_with_warning(monkeypatch):
    async def broken_retrieval(config, payload):
        raise HTTPException(status_code=502, detail="Embedding 请求失败：连接被拒绝")

    captured: dict = {}

    async def fake_completion(config, payload):
        captured.update(payload)
        return {"choices": [{"message": {"role": "assistant", "content": "普通回答"}}]}

    monkeypatch.setattr(chat_proxy, "retrieve_for_chat", broken_retrieval)
    monkeypatch.setattr(chat_proxy, "create_chat_completion", fake_completion)

    response = await chat_proxy.chat_completions(_request(stream=False))

    assert isinstance(response, dict)
    assert "知识库检索失败" in response["retrieval_warning"]
    assert "连接被拒绝" in response["retrieval_warning"]
    # Degraded request must not re-enter the RAG path downstream.
    assert captured["knowledge_id"] is None
    assert response["choices"][0]["message"]["content"] == "普通回答"


@pytest.mark.anyio
async def test_streaming_prepends_warning_frame(monkeypatch):
    async def broken_retrieval(config, payload):
        raise RuntimeError("vector store unreachable")

    async def fake_stream():
        yield b'data: {"choices":[{"delta":{"content":"hi"},"finish_reason":null}]}\n\n'
        yield b"data: [DONE]\n\n"

    async def fake_completion(config, payload):
        return StreamingResponse(fake_stream(), media_type="text/event-stream")

    monkeypatch.setattr(chat_proxy, "retrieve_for_chat", broken_retrieval)
    monkeypatch.setattr(chat_proxy, "create_chat_completion", fake_completion)

    response = await chat_proxy.chat_completions(_request(stream=True))
    frames = [chunk async for chunk in response.body_iterator]

    head = json.loads(frames[0].decode("utf-8").removeprefix("data: "))
    assert "知识库检索失败" in head["retrieval_warning"]
    assert head["choices"][0]["delta"] == {}
    assert frames[-1] == b"data: [DONE]\n\n"


@pytest.mark.anyio
async def test_agent_search_tool_survives_retrieval_failure(monkeypatch):
    async def broken_query(config, model, knowledge_id, query, top_k=4, **kwargs):
        raise HTTPException(status_code=502, detail="Embedding 请求失败")

    monkeypatch.setattr(agent_runner, "query_knowledge", broken_query)

    responses = [
        '{"tool_calls":[{"name":"search_knowledge","parameters":{"query":"请假流程"}}]}',
        '{"action":"final","answer":"知识库暂时不可用，本次未使用知识库。"}',
    ]
    calls = {"count": 0}

    async def fake_completion(config, payload):
        index = min(calls["count"], len(responses) - 1)
        calls["count"] += 1
        return {"choices": [{"message": {"role": "assistant", "content": responses[index]}}]}

    monkeypatch.setattr(agent_runner, "create_chat_completion_full", fake_completion)

    result = await agent_runner.run_agent(
        ProviderConfig(),
        {
            "model": "test",
            "messages": [{"role": "user", "content": "查一下请假流程"}],
            "knowledge_id": "kb-1",
        },
    )

    tool_call = result["agent"]["toolCalls"][0]
    assert tool_call["name"] == "search_knowledge"
    assert "知识库检索失败" in tool_call["output"]["error"]
    assert result["answer"] == "知识库暂时不可用，本次未使用知识库。"
