from __future__ import annotations

import json

from server.db import get_db
from server.schemas.chat import Conversation


def list_chats() -> list[Conversation]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT payload FROM chats ORDER BY updated_at DESC, created_at DESC"
        ).fetchall()

    return [Conversation.model_validate(json.loads(row["payload"])) for row in rows]


def upsert_chat(conversation: Conversation) -> Conversation:
    payload = conversation.model_dump_json()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chats (id, title, payload, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                payload = excluded.payload,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                conversation.id,
                conversation.title,
                payload,
                conversation.createdAt,
                conversation.updatedAt,
            ),
        )

    return conversation


def delete_chat(chat_id: str) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
