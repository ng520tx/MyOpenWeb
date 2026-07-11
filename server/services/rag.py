from __future__ import annotations

from typing import Any

from server.repositories.files import get_file_source, get_file_text
from server.repositories.knowledge import list_knowledge_file_ids
from server.schemas.config import ProviderConfig
from server.services.embeddings import embed_query, embed_texts
from server.services.query_rewrite import needs_rewrite, rewrite_query
from server.services.rerank import rerank_chunks
from server.services.retrieval_grader import grade_retrieval, merge_chunks
from server.services.tokenize import tokenize_for_bm25
from server.vectorstores.factory import get_vector_store

CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
EMBED_BATCH = 16
SOURCE_PREVIEW_LENGTH = 200
# Reciprocal Rank Fusion constant; 60 is the conventional default from the paper.
RRF_K = 60
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


async def index_knowledge(
    config: ProviderConfig,
    embedding_model: str,
    knowledge_id: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> dict[str, Any]:
    """Re-chunk and re-embed every file bound to a knowledge base."""
    store = get_vector_store()
    file_ids = list_knowledge_file_ids(knowledge_id)

    filenames: dict[str, str] = {}
    pending: list[tuple[str, int, str]] = []  # (file_id, chunk_index, content)
    for file_id in file_ids:
        source = get_file_source(file_id)
        filenames[file_id] = source[1] if source else "未知文件"
        text = get_file_text(file_id) or ""
        for index, chunk in enumerate(split_text(text, chunk_size, overlap)):
            pending.append((file_id, index, chunk))

    if not pending:
        store.replace_chunks(knowledge_id, [])
        return {"knowledge_id": knowledge_id, "files": len(file_ids), "chunks": 0}

    contents = [item[2] for item in pending]
    embeddings: list[list[float]] = []
    for batch_start in range(0, len(contents), EMBED_BATCH):
        batch = contents[batch_start:batch_start + EMBED_BATCH]
        embeddings.extend(await embed_texts(config, embedding_model, batch))

    records = [
        {
            "file_id": file_id,
            "filename": filenames.get(file_id, "未知文件"),
            "chunk_index": chunk_index,
            "content": content,
            "embedding": embedding,
            "tokens": tokenize_for_bm25(content),
        }
        for (file_id, chunk_index, content), embedding in zip(pending, embeddings, strict=True)
    ]
    store.replace_chunks(knowledge_id, records)
    return {"knowledge_id": knowledge_id, "files": len(file_ids), "chunks": len(records)}


async def query_knowledge(
    config: ProviderConfig,
    embedding_model: str,
    knowledge_id: str,
    query: str,
    top_k: int = 4,
    mode: str | None = None,
    rerank: bool | None = None,
) -> list[dict[str, Any]]:
    """Return the most relevant chunks for a query.

    Pipeline: vector cosine top-k from the configured VectorStore → optional
    keyword ranking fused via Reciprocal Rank Fusion → optional cross-encoder
    rerank. The store backend (SQLite numpy / pgvector SQL) is transparent to
    this layer. ``mode`` and ``rerank`` override the persisted config (used by
    the debug endpoint and the eval harness for A/B comparisons).
    """
    if not query.strip():
        return []

    retrieval_mode = mode if mode in ("vector", "hybrid") else config.retrieval_mode
    use_rerank = config.rerank_enabled if rerank is None else rerank

    query_vec = await embed_query(config, embedding_model, query)
    if not query_vec:
        return []

    store = get_vector_store()
    # Pull a wider candidate pool than top_k so fusion/rerank has room to work.
    pool_size = max(top_k * 3, 10)
    vector_rows = store.query_by_vector(knowledge_id, query_vec, pool_size)
    if not vector_rows:
        # Empty knowledge base, or embeddings built with a different
        # model/dimension (needs re-index).
        return []

    if retrieval_mode == "hybrid":
        keyword_rows = store.query_by_keywords(knowledge_id, query, pool_size)
        candidates = _fuse_rrf(vector_rows, keyword_rows, pool_size)
    else:
        candidates = [_chunk_result(row, float(row["score"])) for row in vector_rows]

    if use_rerank and candidates:
        reranked = await rerank_chunks(config.rerank_model, query, candidates)
        if reranked is not None:
            candidates = reranked

    return candidates[: max(1, top_k)]


def _chunk_result(row: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "chunk_id": row["id"],
        "file_id": row["file_id"],
        "filename": row["filename"],
        "chunk_index": row["chunk_index"],
        "content": row["content"],
        "score": score,
    }


def _fuse_rrf(
    vector_rows: list[dict[str, Any]],
    keyword_rows: list[dict[str, Any]],
    pool_size: int,
) -> list[dict[str, Any]]:
    """Merge two ranked row lists (vector + keyword) with Reciprocal Rank Fusion."""
    by_id: dict[str, dict[str, Any]] = {}
    rrf_scores: dict[str, float] = {}

    for rank, row in enumerate(vector_rows):
        by_id[row["id"]] = row
        rrf_scores[row["id"]] = rrf_scores.get(row["id"], 0.0) + 1.0 / (RRF_K + rank + 1)

    for rank, row in enumerate(keyword_rows):
        by_id.setdefault(row["id"], row)
        rrf_scores[row["id"]] = rrf_scores.get(row["id"], 0.0) + 1.0 / (RRF_K + rank + 1)

    ordered_ids = sorted(rrf_scores, key=lambda cid: -rrf_scores[cid])
    return [_chunk_result(by_id[cid], rrf_scores[cid]) for cid in ordered_ids[:pool_size]]


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
    if config.query_rewrite_enabled and needs_rewrite(payload.get("messages", [])):
        query = await rewrite_query(config, payload, query)
    top_k = int(payload.get("rag_top_k") or 4)
    chunks = await query_knowledge(config, config.embedding_model, knowledge_id, query, top_k)

    if config.agentic_retrieval_enabled and chunks:
        # Agentic self-correction: grade once, re-retrieve at most once.
        sufficient, followup = await grade_retrieval(
            config, str(payload.get("model", "")), query, chunks
        )
        if not sufficient:
            # 二轮至少检 4 条：top_k 很小时，纠错目标片段常排在 2-4 位。
            extra = await query_knowledge(
                config, config.embedding_model, knowledge_id, followup, max(top_k, 4)
            )
            if extra:
                chunks = merge_chunks(chunks, extra, top_k)

    if not chunks:
        return build_no_context_prompt(base_prompt), []
    return build_rag_system_prompt(base_prompt, chunks), serialize_sources(chunks)
