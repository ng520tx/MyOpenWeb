"""Contract tests every VectorStore backend must pass.

SQLite always runs. The pgvector backend runs when MYOPENWEB_TEST_PG_DSN
points at a PostgreSQL with the vector extension available (CI provides one
via a service container; locally e.g.
``docker run -d -p 5433:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg16``
then MYOPENWEB_TEST_PG_DSN=postgresql://postgres:postgres@localhost:5433/postgres).

Fixtures create real knowledge/file rows in the app database because the
SQLite backend stores chunks in the same database under enforced foreign
keys; the pgvector backend simply ignores those rows.
"""
from __future__ import annotations

import os

import pytest

from server.repositories.files import create_file
from server.repositories.knowledge import bind_file, create_knowledge, delete_knowledge
from server.services.tokenize import tokenize_for_bm25
from server.vectorstores.sqlite_store import SqliteVectorStore

PG_DSN = os.environ.get("MYOPENWEB_TEST_PG_DSN", "").strip()


@pytest.fixture(params=["sqlite", "pgvector"])
def store(request):
    if request.param == "sqlite":
        return SqliteVectorStore()
    if not PG_DSN:
        pytest.skip("MYOPENWEB_TEST_PG_DSN not set")
    pytest.importorskip("psycopg", reason="psycopg not installed")
    from server.vectorstores.pgvector_store import PgVectorStore

    return PgVectorStore(PG_DSN)


@pytest.fixture()
def kb_and_files(store):
    """A knowledge base with two real file rows; store cleaned up afterwards."""
    knowledge = create_knowledge("contract-kb", "vector store contract")
    file_ids: list[str] = []
    for name in ("contract-a.md", "contract-b.md"):
        record = create_file(
            filename=name, raw=name.encode(), mime_type="text/markdown", text_content=name
        )
        bind_file(knowledge.id, record.id)
        file_ids.append(record.id)
    yield knowledge.id, file_ids[0], file_ids[1]
    store.delete_for_knowledge(knowledge.id)
    delete_knowledge(knowledge.id)


def _record(file_id: str, index: int, content: str, embedding: list[float]) -> dict:
    return {
        "file_id": file_id,
        "filename": "contract-doc.md",
        "chunk_index": index,
        "content": content,
        "embedding": embedding,
        "tokens": tokenize_for_bm25(content),
    }


def _seed(store, knowledge_id: str, file_id: str) -> None:
    store.replace_chunks(
        knowledge_id,
        [
            _record(file_id, 0, "数据库连接池耗尽时执行 SHOW PROCESSLIST 检查慢查询。", [1.0, 0.0, 0.0]),
            _record(file_id, 1, "Redis 内存过高时用 redis-cli --bigkeys 定位大 key。", [0.0, 1.0, 0.0]),
            _record(file_id, 2, "SSL 证书到期前替换后执行 nginx -s reload。", [0.0, 0.0, 1.0]),
        ],
    )


def test_replace_count_and_vector_ranking(store, kb_and_files):
    knowledge_id, file_a, _ = kb_and_files
    _seed(store, knowledge_id, file_a)
    assert store.count_chunks(knowledge_id) == 3

    rows = store.query_by_vector(knowledge_id, [0.0, 1.0, 0.0], limit=2)
    assert len(rows) == 2
    assert "redis-cli" in rows[0]["content"]
    assert rows[0]["score"] >= rows[1]["score"]
    assert rows[0]["filename"]

    # replace is a full swap, not an append
    store.replace_chunks(knowledge_id, [_record(file_a, 0, "只剩一条 kafka 记录", [1.0, 0.0, 0.0])])
    assert store.count_chunks(knowledge_id) == 1


def test_keyword_ranking_matches_terms(store, kb_and_files):
    knowledge_id, file_a, _ = kb_and_files
    _seed(store, knowledge_id, file_a)
    rows = store.query_by_keywords(knowledge_id, "bigkeys 大 key", limit=3)
    assert rows
    assert "bigkeys" in rows[0]["content"]


def test_dimension_mismatch_yields_empty(store, kb_and_files):
    knowledge_id, file_a, _ = kb_and_files
    _seed(store, knowledge_id, file_a)
    assert store.query_by_vector(knowledge_id, [1.0] * 8, limit=3) == []


def test_delete_scopes(store, kb_and_files):
    knowledge_id, file_a, file_b = kb_and_files
    other = create_knowledge("contract-kb-2", "second kb")
    bind_file(other.id, file_a)
    try:
        store.replace_chunks(
            knowledge_id,
            [
                _record(file_a, 0, "file A 的内容", [1.0, 0.0]),
                _record(file_b, 0, "file B 的内容", [0.0, 1.0]),
            ],
        )
        store.replace_chunks(other.id, [_record(file_a, 0, "另一个库里 file A 的内容", [1.0, 0.0])])

        # scoped delete: only (knowledge_id, file_a)
        store.delete_for_file(file_a, knowledge_id)
        assert store.count_chunks(knowledge_id) == 1
        assert store.count_chunks(other.id) == 1

        # global delete: file_a everywhere
        store.delete_for_file(file_a)
        assert store.count_chunks(other.id) == 0

        store.delete_for_knowledge(knowledge_id)
        assert store.count_chunks(knowledge_id) == 0
    finally:
        store.delete_for_knowledge(other.id)
        delete_knowledge(other.id)


def test_empty_query_inputs(store):
    assert store.query_by_vector("no-such-kb", [], limit=3) == []
    assert store.query_by_keywords("no-such-kb", "", limit=3) == []
    assert store.query_by_vector("no-such-kb", [1.0, 0.0], limit=3) == []
