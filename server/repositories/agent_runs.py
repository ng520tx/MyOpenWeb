from __future__ import annotations

import json
import time
import uuid
from typing import Any

from server.db import get_db


def _now_ms() -> int:
    return int(time.time() * 1000)


def create_agent_run(
    *,
    conversation_id: str | None,
    message_id: str | None,
    user_message_id: str | None,
    model: str,
    user_input: str,
) -> str:
    run_id = uuid.uuid4().hex
    now = _now_ms()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO agent_runs (
                id, conversation_id, message_id, user_message_id, model,
                user_input, final_answer, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                conversation_id,
                message_id,
                user_message_id,
                model,
                user_input,
                None,
                now,
                now,
            ),
        )
    return run_id


def add_agent_step(
    *,
    run_id: str,
    step_index: int,
    step_type: str,
    name: str | None = None,
    input_data: Any = None,
    output_data: Any = None,
    ok: bool = True,
    error: str | None = None,
) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO agent_steps (
                id, run_id, step_index, type, name, input_json,
                output_json, ok, error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                run_id,
                step_index,
                step_type,
                name,
                json.dumps(input_data, ensure_ascii=False) if input_data is not None else None,
                json.dumps(output_data, ensure_ascii=False) if output_data is not None else None,
                1 if ok else 0,
                error,
                _now_ms(),
            ),
        )


def finish_agent_run(run_id: str, final_answer: str) -> None:
    with get_db() as conn:
        conn.execute(
            """
            UPDATE agent_runs
            SET final_answer = ?, updated_at = ?
            WHERE id = ?
            """,
            (final_answer, _now_ms(), run_id),
        )


def get_agent_run(run_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        run = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            return None

        steps = conn.execute(
            """
            SELECT * FROM agent_steps
            WHERE run_id = ?
            ORDER BY step_index ASC, created_at ASC
            """,
            (run_id,),
        ).fetchall()

    return {
        "id": run["id"],
        "conversation_id": run["conversation_id"],
        "message_id": run["message_id"],
        "user_message_id": run["user_message_id"],
        "model": run["model"],
        "user_input": run["user_input"],
        "final_answer": run["final_answer"],
        "created_at": run["created_at"],
        "updated_at": run["updated_at"],
        "steps": [
            {
                "id": step["id"],
                "run_id": step["run_id"],
                "step_index": step["step_index"],
                "type": step["type"],
                "name": step["name"],
                "input": json.loads(step["input_json"]) if step["input_json"] else None,
                "output": json.loads(step["output_json"]) if step["output_json"] else None,
                "ok": bool(step["ok"]),
                "error": step["error"],
                "created_at": step["created_at"],
            }
            for step in steps
        ],
    }
