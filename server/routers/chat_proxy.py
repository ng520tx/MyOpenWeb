from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from server.repositories.configs import get_provider_config
from server.schemas.chat import ChatCompletionRequest
from server.services.providers import create_chat_completion
from server.services.rag import retrieve_for_chat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

RETRIEVAL_WARNING = "知识库检索失败，本次回答未使用知识库"


@router.post("/chat/completions")
async def chat_completions(payload: ChatCompletionRequest):
    config = get_provider_config()
    data = payload.model_dump()

    sources: list[dict[str, Any]] = []
    retrieval_warning: str | None = None
    if data.get("knowledge_id"):
        try:
            system_prompt, sources = await retrieve_for_chat(config, data)
            data["system_prompt"] = system_prompt
        except Exception as exc:  # embedding service down, vector store unreachable...
            # Retrieval is an enhancement — never let it take the whole chat
            # down with a 502. Degrade to a plain (non-RAG) answer and tell
            # the client so the UI can flag it.
            logger.warning("knowledge retrieval failed, degrading to plain chat: %s", exc)
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            retrieval_warning = f"{RETRIEVAL_WARNING}（{_shorten(str(detail))}）"
            data["knowledge_id"] = None

    response = await create_chat_completion(config, data)

    extra: dict[str, Any] = {}
    if sources:
        extra["sources"] = sources
    if retrieval_warning:
        extra["retrieval_warning"] = retrieval_warning

    if data.get("stream", True):
        if extra and isinstance(response, StreamingResponse):
            return _prepend_frame(response, extra)
        return response

    if isinstance(response, dict) and extra:
        response.update(extra)
    return response


def _shorten(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def _prepend_frame(response: StreamingResponse, extra: dict[str, Any]) -> StreamingResponse:
    """Emit a leading SSE event carrying retrieval metadata (sources and/or a
    degradation warning), then stream the model output unchanged. The frontend
    reads these fields off any chunk."""
    original = response.body_iterator

    async def iterator() -> AsyncIterator[bytes]:
        head = {**extra, "choices": [{"delta": {}, "finish_reason": None}]}
        yield f"data: {json.dumps(head, ensure_ascii=False)}\n\n".encode()
        async for chunk in original:
            yield chunk

    response.body_iterator = iterator()
    return response
