from __future__ import annotations

import time
import uuid

from server.db import get_db
from server.schemas.memory import Memory, MemoryCreate, MemoryUpdate


def _now_ms() -> int:
    return int(time.time() * 1000)


def _row_to_memory(row) -> Memory:
    return Memory(
        id=row["id"],
        content=row["content"],
        category=row["category"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_memories() -> list[Memory]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM memories
            ORDER BY enabled DESC, updated_at DESC
            """
        ).fetchall()
    return [_row_to_memory(row) for row in rows]


def list_enabled_memories() -> list[Memory]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM memories
            WHERE enabled = 1
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [_row_to_memory(row) for row in rows]


def create_memory(payload: MemoryCreate) -> Memory:
    now = _now_ms()
    memory_id = uuid.uuid4().hex
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO memories (id, content, category, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                payload.content.strip(),
                payload.category,
                1 if payload.enabled else 0,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_memory(row)


def update_memory(memory_id: str, payload: MemoryUpdate) -> Memory | None:
    current = get_memory(memory_id)
    if not current:
        return None

    content = payload.content.strip() if payload.content is not None else current.content
    category = payload.category if payload.category is not None else current.category
    enabled = payload.enabled if payload.enabled is not None else current.enabled

    with get_db() as conn:
        conn.execute(
            """
            UPDATE memories
            SET content = ?, category = ?, enabled = ?, updated_at = ?
            WHERE id = ?
            """,
            (content, category, 1 if enabled else 0, _now_ms(), memory_id),
        )
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_memory(row) if row else None


def get_memory(memory_id: str) -> Memory | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_memory(row) if row else None


def delete_memory(memory_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    return cursor.rowcount > 0
