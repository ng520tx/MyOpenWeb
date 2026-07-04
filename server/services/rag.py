from __future__ import annotations

from typing import Any

import numpy as np

from server.repositories.files import get_file_text
from server.repositories.knowledge import (
    list_chunks_for_knowledge,
    list_knowledge_file_ids,
    replace_chunks,
)
from server.schemas.config import ProviderConfig
from server.services.embeddings import embed_query, embed_texts


CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
EMBED_BATCH = 16
SOURCE_PREVIEW_LENGTH = 200
# Boundary characters we prefer to break a chunk on, ordered by priority.
_BREAK_CHARS = ("\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "；", "; ")

RAG_INSTRUCTION = """你是一个企业知识库问答助手。请严格依据下面提供的【参考资料】回答用户问题。
规则：
1. 只能使用参考资料中的信息回答，不要使用资料以外的知识，也不要编造。
2. 如果参考资料中找不到答案，必须直接回答“知识库中没有找到相关信息”，不要猜测。
3. 引用具体内容时，用方括号标注来源序号，例如 [1]、[2]。
4. 回答使用与用户提问相同的语言。"""

NO_CONTEXT_INSTRUCTION = """你是一个企业知识库问答助手。用户选择了一个知识库，但本次没有检索到任何相关资料。
请直接回答“知识库中没有找到相关信息”，并提示用户确认该知识库是否已经上传文件并建立索引。不要编造答案。"""


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, preferring natural boundaries."""
    text = (text or "").strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            window = text[start:end]
            break_at = -1
            for marker in _BREAK_CHARS:
                pos = window.rfind(marker)
                if pos > chunk_size * 0.5:
                    break_at = pos + len(marker)
                    break
            if break_at > 0:
                end = start + break_at

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break
        start = max(end - overlap, start + 1)

    return chunks


async def index_knowledge(config: ProviderConfig, embedding_model: str, knowledge_id: str) -> dict[str, Any]:
    """Re-chunk and re-embed every file bound to a knowledge base."""
    file_ids = list_knowledge_file_ids(knowledge_id)

    pending: list[tuple[str, int, str]] = []  # (file_id, chunk_index, content)
    for file_id in file_ids:
        text = get_file_text(file_id) or ""
        for index, chunk in enumerate(split_text(text)):
            pending.append((file_id, index, chunk))

    if not pending:
        replace_chunks(knowledge_id, [])
        return {"knowledge_id": knowledge_id, "files": len(file_ids), "chunks": 0}

    contents = [item[2] for item in pending]
    embeddings: list[list[float]] = []
    for batch_start in range(0, len(contents), EMBED_BATCH):
        batch = contents[batch_start:batch_start + EMBED_BATCH]
        embeddings.extend(await embed_texts(config, embedding_model, batch))

    records = [
        {
            "file_id": file_id,
            "chunk_index": chunk_index,
            "content": content,
            "embedding": embedding,
        }
        for (file_id, chunk_index, content), embedding in zip(pending, embeddings)
    ]
    replace_chunks(knowledge_id, records)
    return {"knowledge_id": knowledge_id, "files": len(file_ids), "chunks": len(records)}


async def query_knowledge(
    config: ProviderConfig,
    embedding_model: str,
    knowledge_id: str,
    query: str,
    top_k: int = 4,
) -> list[dict[str, Any]]:
    """Return the most relevant chunks for a query via cosine similarity."""
    rows = list_chunks_for_knowledge(knowledge_id)
    if not rows or not query.strip():
        return []

    query_vec = await embed_query(config, embedding_model, query)
    if not query_vec:
        return []

    query_dim = len(query_vec)
    usable = [row for row in rows if len(row["embedding"]) == query_dim]
    if not usable:
        # Embeddings were built with a different model/dimension; needs re-index.
        return []

    matrix = np.asarray([row["embedding"] for row in usable], dtype=np.float32)
    q = np.asarray(query_vec, dtype=np.float32)

    matrix_norms = np.linalg.norm(matrix, axis=1)
    q_norm = np.linalg.norm(q)
    denom = matrix_norms * q_norm
    denom[denom == 0] = 1e-9
    scores = (matrix @ q) / denom

    top_count = max(1, min(top_k, len(usable)))
    top_indices = np.argsort(-scores)[:top_count]

    results: list[dict[str, Any]] = []
    for idx in top_indices:
        row = usable[int(idx)]
        results.append(
            {
                "chunk_id": row["id"],
                "file_id": row["file_id"],
                "filename": row["filename"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "score": float(scores[int(idx)]),
            }
        )
    return results


# ─── chat integration helpers ──────────────────────────────

def last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
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


def build_rag_system_prompt(base_prompt: str | None, chunks: list[dict[str, Any]]) -> str:
    blocks = [
        f"[{index}] 来源：{chunk['filename']}\n{chunk['content']}"
        for index, chunk in enumerate(chunks, start=1)
    ]
    parts = [part for part in (base_prompt,) if part]
    parts.append(RAG_INSTRUCTION)
    parts.append("【参考资料】\n" + "\n\n".join(blocks))
    return "\n\n".join(parts)


def build_no_context_prompt(base_prompt: str | None) -> str:
    parts = [part for part in (base_prompt,) if part]
    parts.append(NO_CONTEXT_INSTRUCTION)
    return "\n\n".join(parts)


def serialize_sources(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "file_id": chunk["file_id"],
            "filename": chunk["filename"],
            "chunk_index": chunk["chunk_index"],
            "score": round(chunk["score"], 4),
            "preview": chunk["content"][:SOURCE_PREVIEW_LENGTH],
        }
        for index, chunk in enumerate(chunks, start=1)
    ]


async def retrieve_for_chat(
    config: ProviderConfig, payload: dict[str, Any]
) -> tuple[str | None, list[dict[str, Any]]]:
    """Return an augmented system prompt and the serialized sources for a chat
    request that selected a knowledge base. Falls back to a 'no info' prompt
    when nothing relevant is found so the model refuses instead of guessing."""
    knowledge_id = payload.get("knowledge_id")
    base_prompt = payload.get("system_prompt")
    if not knowledge_id:
        return base_prompt, []

    query = last_user_text(payload.get("messages", []))
    top_k = int(payload.get("rag_top_k") or 4)
    chunks = await query_knowledge(config, config.embedding_model, knowledge_id, query, top_k)
    if not chunks:
        return build_no_context_prompt(base_prompt), []
    return build_rag_system_prompt(base_prompt, chunks), serialize_sources(chunks)
