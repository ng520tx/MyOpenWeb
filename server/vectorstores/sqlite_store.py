"""Default VectorStore: chunks live in the app's SQLite database.

Embeddings are stored as JSON arrays and ranked with an in-process numpy
cosine; keyword ranking rides SQLite FTS5 (BM25) over pre-tokenized text.
Zero extra services — matches the "lightweight intranet single instance"
deployment target.

The numpy matrix per knowledge base is cached in-process and validated with a
cheap version stamp, so repeat queries skip the row reload and JSON parsing
while re-indexes (even from another process on the shared SQLite file, e.g.
the MCP server) are picked up on the very next query.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import time
import uuid
from typing import Any

import numpy as np

from server.db import get_db
from server.services.tokenize import build_match_query


def _now_ms() -> int:
    return int(time.time() * 1000)


class SqliteVectorStore:
    backend = "sqlite"

    def __init__(self) -> None:
        # knowledge_id → {"stamp", "rows", "by_dim": {dim: (indices, matrix, norms)}}
        self._cache: dict[str, dict[str, Any]] = {}

    # ─── persistence ───────────────────────────────────────

    def replace_chunks(self, knowledge_id: str, records: list[dict[str, Any]]) -> None:
        now = _now_ms()
        chunk_rows: list[tuple] = []
        fts_rows: list[tuple] = []
        for record in records:
            chunk_id = uuid.uuid4().hex
            chunk_rows.append(
                (
                    chunk_id,
                    knowledge_id,
                    record["file_id"],
                    record["chunk_index"],
                    record["content"],
                    json.dumps(record["embedding"]),
                    now,
                )
            )
            fts_rows.append((chunk_id, knowledge_id, record.get("tokens") or ""))

        with get_db() as conn:
            conn.execute("DELETE FROM chunks WHERE knowledge_id = ?", (knowledge_id,))
            self._fts_delete_for_knowledge(conn, knowledge_id)
            conn.executemany(
                """
                INSERT INTO chunks (id, knowledge_id, file_id, chunk_index, content, embedding, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                chunk_rows,
            )
            with contextlib.suppress(sqlite3.OperationalError):
                conn.executemany(
                    "INSERT INTO chunks_fts (chunk_id, knowledge_id, tokens) VALUES (?, ?, ?)",
                    fts_rows,
                )
        self._cache.pop(knowledge_id, None)

    def count_chunks(self, knowledge_id: str) -> int:
        with get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM chunks WHERE knowledge_id = ?",
                (knowledge_id,),
            ).fetchone()
        return row["c"]

    def delete_for_knowledge(self, knowledge_id: str) -> None:
        with get_db() as conn:
            self._fts_delete_for_knowledge(conn, knowledge_id)
            conn.execute("DELETE FROM chunks WHERE knowledge_id = ?", (knowledge_id,))
        self._cache.pop(knowledge_id, None)

    def delete_for_file(self, file_id: str, knowledge_id: str | None = None) -> None:
        with get_db() as conn:
            # FTS5 virtual tables have no foreign keys; mirror rows go first,
            # while the chunk ids they point at still exist.
            if knowledge_id is None:
                with contextlib.suppress(sqlite3.OperationalError):
                    conn.execute(
                        "DELETE FROM chunks_fts WHERE chunk_id IN (SELECT id FROM chunks WHERE file_id = ?)",
                        (file_id,),
                    )
                conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
            else:
                with contextlib.suppress(sqlite3.OperationalError):
                    conn.execute(
                        """
                        DELETE FROM chunks_fts WHERE chunk_id IN (
                            SELECT id FROM chunks WHERE knowledge_id = ? AND file_id = ?
                        )
                        """,
                        (knowledge_id, file_id),
                    )
                conn.execute(
                    "DELETE FROM chunks WHERE knowledge_id = ? AND file_id = ?",
                    (knowledge_id, file_id),
                )
        if knowledge_id is None:
            self._cache.clear()
        else:
            self._cache.pop(knowledge_id, None)

    # ─── ranking primitives ────────────────────────────────

    def query_by_vector(
        self, knowledge_id: str, vector: list[float], limit: int
    ) -> list[dict[str, Any]]:
        cached = self._load_rows(knowledge_id)
        if cached is None or not vector:
            return []
        indices, matrix, norms = self._vectors_for_dim(cached, len(vector))
        if not indices:
            # Embeddings were built with a different model/dimension; needs re-index.
            return []

        rows = cached["rows"]
        q = np.asarray(vector, dtype=np.float32)
        q_norm = float(np.linalg.norm(q)) or 1e-9
        scores = (matrix @ q) / (norms * q_norm)

        order = np.argsort(-scores)[: min(limit, len(indices))]
        return [
            {**self._public_row(rows[indices[int(i)]]), "score": float(scores[int(i)])}
            for i in order
        ]

    def query_by_keywords(
        self, knowledge_id: str, text: str, limit: int
    ) -> list[dict[str, Any]]:
        match_query = build_match_query(text)
        if not match_query.strip():
            return []
        try:
            with get_db() as conn:
                id_rows = conn.execute(
                    """
                    SELECT chunk_id
                    FROM chunks_fts
                    WHERE chunks_fts MATCH ? AND knowledge_id = ?
                    ORDER BY bm25(chunks_fts)
                    LIMIT ?
                    """,
                    (match_query, knowledge_id, limit),
                ).fetchall()
        except sqlite3.OperationalError:
            # SQLite compiled without FTS5: hybrid degrades to vector-only.
            return []

        cached = self._load_rows(knowledge_id)
        if cached is None:
            return []
        by_id = {row["id"]: row for row in cached["rows"]}
        results: list[dict[str, Any]] = []
        for rank, id_row in enumerate(id_rows):
            row = by_id.get(id_row["chunk_id"])
            if row is None:
                continue  # stale FTS row
            # BM25 rank order is what fusion consumes; expose a simple
            # descending pseudo-score for standalone callers.
            results.append({**self._public_row(row), "score": 1.0 / (rank + 1)})
        return results

    # ─── cache internals ───────────────────────────────────

    def _stamp(self, knowledge_id: str) -> tuple[int, int, str]:
        """Cheap version stamp: replace_chunks swaps all rows with fresh random
        ids and a new created_at, so (count, max created_at, min id) changes on
        every re-index — including ones done by other processes."""
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c, COALESCE(MAX(created_at), 0) AS m, COALESCE(MIN(id), '') AS i
                FROM chunks WHERE knowledge_id = ?
                """,
                (knowledge_id,),
            ).fetchone()
        return row["c"], row["m"], row["i"]

    def _load_rows(self, knowledge_id: str) -> dict[str, Any] | None:
        stamp = self._stamp(knowledge_id)
        if stamp[0] == 0:
            self._cache.pop(knowledge_id, None)
            return None
        cached = self._cache.get(knowledge_id)
        if cached is None or cached["stamp"] != stamp:
            cached = {
                "stamp": stamp,
                "rows": self._fetch_rows(knowledge_id),
                "by_dim": {},
            }
            self._cache[knowledge_id] = cached
        return cached

    def _fetch_rows(self, knowledge_id: str) -> list[dict[str, Any]]:
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

    @staticmethod
    def _vectors_for_dim(cached: dict[str, Any], dim: int) -> tuple[list[int], Any, Any]:
        entry = cached["by_dim"].get(dim)
        if entry is None:
            rows = cached["rows"]
            indices = [i for i, row in enumerate(rows) if len(row["embedding"]) == dim]
            if indices:
                matrix = np.asarray([rows[i]["embedding"] for i in indices], dtype=np.float32)
                norms = np.linalg.norm(matrix, axis=1)
                norms[norms == 0] = 1e-9
                entry = (indices, matrix, norms)
            else:
                entry = ([], None, None)
            cached["by_dim"][dim] = entry
        return entry

    @staticmethod
    def _public_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "file_id": row["file_id"],
            "filename": row["filename"],
            "chunk_index": row["chunk_index"],
            "content": row["content"],
        }

    @staticmethod
    def _fts_delete_for_knowledge(conn, knowledge_id: str) -> None:
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute("DELETE FROM chunks_fts WHERE knowledge_id = ?", (knowledge_id,))
