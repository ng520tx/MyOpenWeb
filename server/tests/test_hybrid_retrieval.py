"""End-to-end hybrid retrieval over a real (sandboxed) SQLite database,
with embeddings stubbed so no model service is required."""
from __future__ import annotations

import pytest

import server.services.rag as rag
from server.repositories.files import create_file
from server.repositories.knowledge import (
    bind_file,
    create_knowledge,
    replace_chunks,
    search_chunks_bm25,
)
from server.schemas.config import ProviderConfig
from server.services.tokenize import build_match_query, tokenize_for_bm25


DOCS = [
    "数据库连接池耗尽时，先执行 SHOW PROCESSLIST 检查 MySQL 慢查询。",
    "Redis 内存占用过高时，用 redis-cli --bigkeys 定位大 key。",
    "SSL 证书到期前 30 天会收到续期提醒邮件，替换后执行 nginx -s reload。",
]

# Orthogonal fake embeddings: doc i points along axis i.
def _fake_vector(index: int, dim: int = 4) -> list[float]:
    vec = [0.0] * dim
    vec[index % dim] = 1.0
    return vec


@pytest.fixture()
def knowledge_id() -> str:
    knowledge = create_knowledge("test-kb", "hybrid retrieval test")
    file_record = create_file(
        filename="test-doc.md",
        raw="\n".join(DOCS).encode("utf-8"),
        mime_type="text/markdown",
        text_content="\n".join(DOCS),
    )
    bind_file(knowledge.id, file_record.id)
    replace_chunks(
        knowledge.id,
        [
            {
                "file_id": file_record.id,
                "chunk_index": index,
                "content": content,
                "embedding": _fake_vector(index),
                "tokens": tokenize_for_bm25(content),
            }
            for index, content in enumerate(DOCS)
        ],
    )
    return knowledge.id


def test_bm25_finds_exact_terms(knowledge_id: str):
    ids = search_chunks_bm25(knowledge_id, build_match_query("bigkeys 大 key"), limit=3)
    assert ids, "BM25 should match the Redis chunk"


@pytest.mark.anyio
async def test_hybrid_query_prefers_keyword_match(knowledge_id: str, monkeypatch):
    # Query vector points at doc 0 (the MySQL chunk) even though the question
    # is about Redis — hybrid BM25 fusion must still surface the Redis chunk first.
    async def fake_embed_query(config, model, text):
        return _fake_vector(0)

    monkeypatch.setattr(rag, "embed_query", fake_embed_query)
    config = ProviderConfig(retrieval_mode="hybrid")

    results = await rag.query_knowledge(
        config, "fake-model", knowledge_id, "redis bigkeys 大 key 怎么查", top_k=1, mode="hybrid"
    )
    assert results
    assert "bigkeys" in results[0]["content"]


@pytest.mark.anyio
async def test_vector_mode_follows_embedding_only(knowledge_id: str, monkeypatch):
    async def fake_embed_query(config, model, text):
        return _fake_vector(2)  # points at the SSL chunk

    monkeypatch.setattr(rag, "embed_query", fake_embed_query)
    config = ProviderConfig(retrieval_mode="vector")

    results = await rag.query_knowledge(
        config, "fake-model", knowledge_id, "证书", top_k=1, mode="vector"
    )
    assert results
    assert "SSL 证书" in results[0]["content"]


@pytest.mark.anyio
async def test_dimension_mismatch_returns_empty(knowledge_id: str, monkeypatch):
    async def fake_embed_query(config, model, text):
        return [1.0] * 8  # different dimension → stale index guard

    monkeypatch.setattr(rag, "embed_query", fake_embed_query)
    config = ProviderConfig()

    results = await rag.query_knowledge(
        config, "fake-model", knowledge_id, "任何问题", top_k=2
    )
    assert results == []
