from __future__ import annotations

import json
import time
import uuid
from typing import Any

from server.db import get_db
from server.repositories.files import _row_to_record  # reuse file row mapping
from server.schemas.file import FileRecord
from server.schemas.knowledge import Knowledge, KnowledgeDetail


def _now_ms() -> int:
    return int(time.time() * 1000)


def _row_to_knowledge(row, file_count: int, chunk_count: int) -> Knowledge:
    return Knowledge(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        file_count=file_count,
        chunk_count=chunk_count,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _counts(conn, knowledge_id: str) -> tuple[int, int]:
    file_count = conn.execute(
        "SELECT COUNT(*) AS c FROM knowledge_file WHERE knowledge_id = ?",
        (knowledge_id,),
    ).fetchone()["c"]
    chunk_count = conn.execute(
        "SELECT COUNT(*) AS c FROM chunks WHERE knowledge_id = ?",
        (knowledge_id,),
    ).fetchone()["c"]
    return file_count, chunk_count


# ─── knowledge base CRUD ───────────────────────────────────

def create_knowledge(name: str, description: str = "") -> Knowledge:
    knowledge_id = uuid.uuid4().hex
    now = _now_ms()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO knowledge (id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (knowledge_id, name.strip(), description.strip(), now, now),
        )
        row = conn.execute("SELECT * FROM knowledge WHERE id = ?", (knowledge_id,)).fetchone()
        file_count, chunk_count = _counts(conn, knowledge_id)
    return _row_to_knowledge(row, file_count, chunk_count)


def list_knowledge() -> list[Knowledge]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM knowledge ORDER BY updated_at DESC").fetchall()
        result = []
        for row in rows:
            file_count, chunk_count = _counts(conn, row["id"])
            result.append(_row_to_knowledge(row, file_count, chunk_count))
    return result


def get_knowledge(knowledge_id: str) -> KnowledgeDetail | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM knowledge WHERE id = ?", (knowledge_id,)).fetchone()
        if not row:
            return None
        file_count, chunk_count = _counts(conn, knowledge_id)
        file_rows = conn.execute(
            """
            SELECT f.* FROM files f
            JOIN knowledge_file kf ON kf.file_id = f.id
            WHERE kf.knowledge_id = ?
            ORDER BY kf.created_at DESC
            """,
            (knowledge_id,),
        ).fetchall()
    base = _row_to_knowledge(row, file_count, chunk_count)
    files: list[FileRecord] = [_row_to_record(file_row) for file_row in file_rows]
    return KnowledgeDetail(**base.model_dump(), files=files)


def update_knowledge(knowledge_id: str, name: str | None, description: str | None) -> Knowledge | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM knowledge WHERE id = ?", (knowledge_id,)).fetchone()
        if not row:
            return None
        next_name = name.strip() if name is not None else row["name"]
        next_desc = description.strip() if description is not None else (row["description"] or "")
        conn.execute(
            "UPDATE knowledge SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (next_name, next_desc, _now_ms(), knowledge_id),
        )
        updated = conn.execute("SELECT * FROM knowledge WHERE id = ?", (knowledge_id,)).fetchone()
        file_count, chunk_count = _counts(conn, knowledge_id)
    return _row_to_knowledge(updated, file_count, chunk_count)


def delete_knowledge(knowledge_id: str) -> bool:
    with get_db() as conn:
        conn.execute("DELETE FROM chunks WHERE knowledge_id = ?", (knowledge_id,))
        conn.execute("DELETE FROM knowledge_file WHERE knowledge_id = ?", (knowledge_id,))
        cursor = conn.execute("DELETE FROM knowledge WHERE id = ?", (knowledge_id,))
    return cursor.rowcount > 0


def knowledge_exists(knowledge_id: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM knowledge WHERE id = ?", (knowledge_id,)).fetchone()
    return row is not None


# ─── file binding ──────────────────────────────────────────

def bind_file(knowledge_id: str, file_id: str) -> bool:
    with get_db() as conn:
        file_row = conn.execute("SELECT 1 FROM files WHERE id = ?", (file_id,)).fetchone()
        kb_row = conn.execute("SELECT 1 FROM knowledge WHERE id = ?", (knowledge_id,)).fetchone()
        if not file_row or not kb_row:
            return False
        conn.execute(
            """
            INSERT OR IGNORE INTO knowledge_file (knowledge_id, file_id, created_at)
            VALUES (?, ?, ?)
            """,
            (knowledge_id, file_id, _now_ms()),
        )
        conn.execute(
            "UPDATE knowledge SET updated_at = ? WHERE id = ?",
            (_now_ms(), knowledge_id),
        )
    return True


def unbind_file(knowledge_id: str, file_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM knowledge_file WHERE knowledge_id = ? AND file_id = ?",
            (knowledge_id, file_id),
        )
        # Drop any stale chunks belonging to the now-detached file.
        conn.execute(
            "DELETE FROM chunks WHERE knowledge_id = ? AND file_id = ?",
            (knowledge_id, file_id),
        )
        conn.execute(
            "UPDATE knowledge SET updated_at = ? WHERE id = ?",
            (_now_ms(), knowledge_id),
        )
    return cursor.rowcount > 0


def list_knowledge_file_ids(knowledge_id: str) -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT file_id FROM knowledge_file WHERE knowledge_id = ? ORDER BY created_at ASC",
            (knowledge_id,),
        ).fetchall()
    return [row["file_id"] for row in rows]


# ─── chunks / index ────────────────────────────────────────

def replace_chunks(knowledge_id: str, records: list[dict[str, Any]]) -> None:
    """Atomically swap all chunks of a knowledge base with a fresh set.

    Each record: {file_id, chunk_index, content, embedding(list[float])}
    """
    now = _now_ms()
    with get_db() as conn:
        conn.execute("DELETE FROM chunks WHERE knowledge_id = ?", (knowledge_id,))
        conn.executemany(
            """
            INSERT INTO chunks (id, knowledge_id, file_id, chunk_index, content, embedding, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    uuid.uuid4().hex,
                    knowledge_id,
                    record["file_id"],
                    record["chunk_index"],
                    record["content"],
                    json.dumps(record["embedding"]),
                    now,
                )
                for record in records
            ],
        )


def list_chunks_for_knowledge(knowledge_id: str) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.file_id, c.chunk_index, c.content, c.embedding, f.filename
            FROM chunks c
            LEFT JOIN files f ON f.id = c.file_id
            WHERE c.knowledge_id = ?
            ORDER BY c.file_id, c.chunk_index
            """,
            (knowledge_id,),
        ).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        try:
            embedding = json.loads(row["embedding"])
        except (json.JSONDecodeError, TypeError):
            continue
        result.append(
            {
                "id": row["id"],
                "file_id": row["file_id"],
                "filename": row["filename"] or "未知文件",
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "embedding": embedding,
            }
        )
    return result
