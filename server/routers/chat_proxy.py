from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from server.repositories.configs import get_provider_config
from server.schemas.chat import ChatCompletionRequest
from server.services.providers import create_chat_completion
from server.services.rag import retrieve_for_chat


router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat/completions")
async def chat_completions(payload: ChatCompletionRequest):
    config = get_provider_config()
    data = payload.model_dump()

    sources: list[dict[str, Any]] = []
    if data.get("knowledge_id"):
        system_prompt, sources = await retrieve_for_chat(config, data)
        data["system_prompt"] = system_prompt

    response = await create_chat_completion(config, data)

    if data.get("stream", True):
        if sources and isinstance(response, StreamingResponse):
            return _prepend_sources(response, sources)
        return response

    if isinstance(response, dict) and sources:
        response["sources"] = sources
    return response


def _prepend_sources(response: StreamingResponse, sources: list[dict[str, Any]]) -> StreamingResponse:
    """Emit a leading SSE event carrying the retrieval sources, then stream the
    model output unchanged. The frontend reads ``sources`` off any chunk."""
    original = response.body_iterator

    async def iterator() -> AsyncIterator[bytes]:
        head = {"sources": sources, "choices": [{"delta": {}, "finish_reason": None}]}
        yield f"data: {json.dumps(head, ensure_ascii=False)}\n\n".encode("utf-8")
        async for chunk in original:
            yield chunk

    response.body_iterator = iterator()
    return response
