"""The in-process vector cache must serve repeat queries without reloading
rows, yet pick up a re-index (chunk swap) on the very next query."""
from __future__ import annotations

import pytest

import server.services.rag as rag
from server.repositories.files import create_file
from server.repositories.knowledge import bind_file, create_knowledge, replace_chunks
from server.schemas.config import ProviderConfig
from server.services.tokenize import tokenize_for_bm25


def _chunks(file_id: str, contents: list[str]) -> list[dict]:
    return [
        {
            "file_id": file_id,
            "chunk_index": index,
            "content": content,
            "embedding": [1.0, 0.0],
            "tokens": tokenize_for_bm25(content),
        }
        for index, content in enumerate(contents)
    ]


@pytest.mark.anyio
async def test_cache_hits_and_reindex_invalidation(monkeypatch):
    knowledge = create_knowledge("cache-kb", "vector cache test")
    record = create_file(
        filename="cache-doc.md",
        raw=b"v1",
        mime_type="text/markdown",
        text_content="v1",
    )
    bind_file(knowledge.id, record.id)
    replace_chunks(knowledge.id, _chunks(record.id, ["旧版本内容 v1"]))

    async def fake_embed_query(config, model, text):
        return [1.0, 0.0]

    monkeypatch.setattr(rag, "embed_query", fake_embed_query)
    load_calls = 0
    real_loader = rag.list_chunks_for_knowledge

    def counting_loader(knowledge_id):
        nonlocal load_calls
        load_calls += 1
        return real_loader(knowledge_id)

    monkeypatch.setattr(rag, "list_chunks_for_knowledge", counting_loader)
    config = ProviderConfig()

    first = await rag.query_knowledge(config, "fake", knowledge.id, "内容", top_k=1, mode="vector")
    assert first and "v1" in first[0]["content"]
    assert load_calls == 1

    # Same stamp → repeat query must not reload rows from SQLite.
    second = await rag.query_knowledge(config, "fake", knowledge.id, "内容", top_k=1, mode="vector")
    assert second and "v1" in second[0]["content"]
    assert load_calls == 1

    # Re-index swaps every chunk row; the stamp changes and the next query
    # must serve the new content.
    replace_chunks(knowledge.id, _chunks(record.id, ["新版本内容 v2"]))
    third = await rag.query_knowledge(config, "fake", knowledge.id, "内容", top_k=1, mode="vector")
    assert third and "v2" in third[0]["content"]
    assert load_calls == 2

    # Empty knowledge base drops the cache entry and returns nothing.
    replace_chunks(knowledge.id, [])
    assert await rag.query_knowledge(config, "fake", knowledge.id, "内容", top_k=1) == []
