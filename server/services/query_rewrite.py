"""Multi-turn query rewriting for RAG retrieval.

In a follow-up turn like "它的默认端口是多少", the raw user text loses the
subject established earlier in the conversation, so both BM25 and vector
retrieval miss. Before retrieving we ask the chat model to rewrite the last
user turn into a self-contained query using recent history.

Design notes:
- Single-turn conversations skip the extra LLM call entirely.
- Any failure (timeout, empty/garbage output) falls back to the raw query, so
  retrieval never breaks because of the rewriter.
"""
from __future__ import annotations

import logging
from typing import Any

from server.schemas.config import ProviderConfig
from server.services.providers import create_chat_completion_text

logger = logging.getLogger(__name__)

# Keep the rewrite call cheap: last 3 exchanges, each turn clipped.
MAX_HISTORY_MESSAGES = 6
MAX_TURN_CHARS = 500
MAX_REWRITTEN_CHARS = 200

REWRITE_INSTRUCTION = """你是检索查询改写器。根据对话历史，把用户最后的问题改写成一条独立、完整、适合在知识库中检索的查询：
- 补全代词和省略的主语（例如把“它的端口”改成具体对象的端口）。
- 保留原有的关键词和语言，不要回答问题本身。
- 只输出改写后的查询文本，不要任何解释、引号或前缀。
如果最后的问题本身已经完整，原样输出即可。"""


def _text_of(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def _history_for_rewrite(messages: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Collect (role, text) turns before the final user message."""
    turns = [
        (str(message.get("role")), _text_of(message).strip())
        for message in messages
        if message.get("role") in ("user", "assistant") and _text_of(message).strip()
    ]
    return turns[:-1] if turns else []


def needs_rewrite(messages: list[dict[str, Any]]) -> bool:
    """Only multi-turn conversations benefit; the first question is used as-is."""
    return len(_history_for_rewrite(messages)) > 0


async def rewrite_query(
    config: ProviderConfig,
    payload: dict[str, Any],
    raw_query: str,
) -> str:
    messages = payload.get("messages", [])
    history = _history_for_rewrite(messages)
    if not history or not raw_query.strip():
        return raw_query

    recent = history[-MAX_HISTORY_MESSAGES:]
    lines = [
        f"{'用户' if role == 'user' else '助手'}：{text[:MAX_TURN_CHARS]}"
        for role, text in recent
    ]
    prompt = (
        "对话历史：\n" + "\n".join(lines) + f"\n\n用户最后的问题：{raw_query.strip()}"
    )

    try:
        rewritten = await create_chat_completion_text(
            config,
            {
                "model": payload.get("model", ""),
                "messages": [{"role": "user", "content": prompt}],
                "system_prompt": REWRITE_INSTRUCTION,
                "temperature": 0.0,
                "max_tokens": 128,
                "stream": False,
            },
        )
    except Exception as exc:  # noqa: BLE001 - retrieval must survive rewriter failures
        logger.warning("query rewrite failed, falling back to raw query: %s", exc)
        return raw_query

    cleaned = rewritten.strip().strip('"').strip("“”").splitlines()[0].strip() if rewritten.strip() else ""
    if not cleaned or len(cleaned) > MAX_REWRITTEN_CHARS:
        return raw_query
    return cleaned
