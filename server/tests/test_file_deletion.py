"""Deleting a file must not leave orphan chunks behind in any knowledge base.

Regression for the bug where SQLite foreign keys were never enabled: the
schema's ON DELETE CASCADE was silently ignored, so deleted files kept
surfacing in retrieval as "未知文件" chunks.
"""
from __future__ import annotations

import sqlite3

import pytest

from server.db import get_db
from server.repositories.files import create_file, delete_file
from server.repositories.knowledge import (
    bind_file,
    create_knowledge,
    list_knowledge_file_ids,
)
from server.services.tokenize import tokenize_for_bm25
from server.vectorstores.factory import get_vector_store


def _make_indexed_file(knowledge_id: str, content: str) -> str:
    record = create_file(
        filename="deleted-doc.md",
        raw=content.encode("utf-8"),
        mime_type="text/markdown",
        text_content=content,
    )
    bind_file(knowledge_id, record.id)
    get_vector_store().replace_chunks(
        knowledge_id,
        [
            {
                "file_id": record.id,
                "filename": record.filename,
                "chunk_index": 0,
                "content": content,
                "embedding": [1.0, 0.0, 0.0, 0.0],
                "tokens": tokenize_for_bm25(content),
            }
        ],
    )
    return record.id


def test_delete_file_removes_chunks_binding_and_keyword_index():
    knowledge = create_knowledge("delete-test-kb", "orphan chunk regression")
    content = "Kafka 消费积压时先检查 consumer group 的 lag 指标。"
    file_id = _make_indexed_file(knowledge.id, content)
    store = get_vector_store()

    assert store.count_chunks(knowledge.id) == 1, "precondition: index built"

    assert delete_file(file_id) is True

    assert store.count_chunks(knowledge.id) == 0
    assert store.query_by_vector(knowledge.id, [1.0, 0.0, 0.0, 0.0], limit=5) == []
    assert store.query_by_keywords(knowledge.id, "kafka lag", limit=5) == []
    assert list_knowledge_file_ids(knowledge.id) == []


def test_foreign_keys_are_enforced():
    with get_db() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO chunks (id, knowledge_id, file_id, chunk_index, content, embedding, created_at)
                VALUES ('orphan', 'no-such-kb', 'no-such-file', 0, 'x', '[]', 0)
                """
            )
