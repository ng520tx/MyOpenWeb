from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from server.db import DATA_DIR, get_db
from server.schemas.file import FileDetail, FileRecord


FILES_DIR = DATA_DIR / "files"
PREVIEW_LENGTH = 200


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ensure_dir() -> None:
    FILES_DIR.mkdir(parents=True, exist_ok=True)


def _row_to_record(row) -> FileRecord:
    text_content = row["text_content"] or ""
    meta = json.loads(row["meta_json"]) if row["meta_json"] else {}
    return FileRecord(
        id=row["id"],
        filename=row["filename"],
        mime_type=row["mime_type"],
        size=row["size"],
        hash=row["hash"],
        text_preview=text_content[:PREVIEW_LENGTH],
        text_length=len(text_content),
        meta=meta,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_detail(row) -> FileDetail:
    record = _row_to_record(row)
    return FileDetail(**record.model_dump(), text_content=row["text_content"] or "")


def create_file(
    *,
    filename: str,
    raw: bytes,
    mime_type: str | None,
    text_content: str,
    meta: dict[str, Any] | None = None,
) -> FileRecord:
    _ensure_dir()
    file_id = uuid.uuid4().hex
    now = _now_ms()
    file_hash = hashlib.sha256(raw).hexdigest()
    suffix = Path(filename).suffix
    stored_path = FILES_DIR / f"{file_id}{suffix}"
    stored_path.write_bytes(raw)
    meta_json = json.dumps(meta or {}, ensure_ascii=False)

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO files (
                id, filename, path, mime_type, size, hash,
                text_content, meta_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                filename,
                str(stored_path),
                mime_type,
                len(raw),
                file_hash,
                text_content,
                meta_json,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    return _row_to_record(row)


def list_files() -> list[FileRecord]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM files ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_record(row) for row in rows]


def get_file(file_id: str) -> FileDetail | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    return _row_to_detail(row) if row else None


def get_file_text(file_id: str) -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT text_content FROM files WHERE id = ?", (file_id,)
        ).fetchone()
    if not row:
        return None
    return row["text_content"] or ""


def get_file_source(file_id: str) -> tuple[str, str, str | None] | None:
    """Return (stored_path, filename, mime_type) so a file can be re-extracted."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT path, filename, mime_type FROM files WHERE id = ?", (file_id,)
        ).fetchone()
    if not row:
        return None
    return row["path"], row["filename"], row["mime_type"]


def update_file_text(file_id: str, text_content: str) -> FileRecord | None:
    now = _now_ms()
    with get_db() as conn:
        conn.execute(
            "UPDATE files SET text_content = ?, updated_at = ? WHERE id = ?",
            (text_content, now, file_id),
        )
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    return _row_to_record(row) if row else None


def delete_file(file_id: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT path FROM files WHERE id = ?", (file_id,)).fetchone()
        if not row:
            return False
        cursor = conn.execute("DELETE FROM files WHERE id = ?", (file_id,))

    stored_path = row["path"]
    if stored_path:
        try:
            Path(stored_path).unlink(missing_ok=True)
        except OSError:
            pass
    return cursor.rowcount > 0
