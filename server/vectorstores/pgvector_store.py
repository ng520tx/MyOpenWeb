"""PostgreSQL + pgvector VectorStore for beyond-single-box scale.

Vector ranking is a single SQL statement (``ORDER BY embedding <=> $q``,
cosine distance) instead of the in-process numpy scan; keyword ranking uses a
generated tsvector column over the same pre-tokenized text the SQLite backend
feeds FTS5, so hybrid retrieval keeps working after the switch.

Design notes:

- ``vector`` column is declared without a fixed dimension and a ``dim`` column
  filters mismatched embeddings (same "changed embedding model → empty result,
  re-index" contract as the SQLite backend). Pinning a dimension (required for
  an HNSW/IVFFlat index at larger scale) is a one-line schema change once the
  embedding model is settled.
- The driver is sync psycopg3, matching the repository layer's sync SQLite
  style; a single autocommit connection per process is enough for the target
  concurrency and is lazily re-established when the server drops it.
- ``filename`` is denormalized into the chunk row because the files table
  stays in SQLite — the relational app data does not migrate, only vectors.

Requires ``pip install -r server/requirements-pgvector.txt`` and
``MYOPENWEB_VECTOR_BACKEND=pgvector`` + ``MYOPENWEB_PG_DSN=postgresql://...``.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from server.services.tokenize import tokenize_for_bm25

_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    knowledge_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    filename TEXT NOT NULL DEFAULT '',
    tokens TEXT NOT NULL DEFAULT '',
    tokens_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', tokens)) STORED,
    dim INTEGER NOT NULL,
    embedding vector NOT NULL,
    created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_knowledge_idx ON chunks(knowledge_id);
CREATE INDEX IF NOT EXISTS chunks_file_idx ON chunks(file_id);
CREATE INDEX IF NOT EXISTS chunks_tokens_tsv_idx ON chunks USING GIN (tokens_tsv);
"""


def _to_pgvector(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"


class PgVectorStore:
    backend = "pgvector"

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg  # noqa: F401
        except ImportError as exc:  # pragma: no cover - guarded by factory usage
            raise RuntimeError(
                "pgvector 后端需要 psycopg：pip install -r server/requirements-pgvector.txt"
            ) from exc
        self._dsn = dsn
        self._conn = None
        self._lock = threading.Lock()
        self._ensure_schema()

    # ─── connection management ─────────────────────────────

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn, autocommit=True)

    def _execute(self, query: str, params: tuple = (), fetch: bool = False):
        """Run one statement on the shared connection, reconnecting once if the
        server dropped it (restart, idle timeout)."""
        import psycopg

        with self._lock:
            for attempt in (1, 2):
                if self._conn is None or self._conn.closed:
                    self._conn = self._connect()
                try:
                    with self._conn.cursor() as cursor:
                        cursor.execute(query, params)
                        return cursor.fetchall() if fetch else None
                except psycopg.OperationalError:
                    self._conn = None
                    if attempt == 2:
                        raise

    def _ensure_schema(self) -> None:
        self._execute(_SCHEMA)

    # ─── persistence ───────────────────────────────────────

    def replace_chunks(self, knowledge_id: str, records: list[dict[str, Any]]) -> None:
        import psycopg

        now = int(time.time() * 1000)
        with self._lock:
            if self._conn is None or self._conn.closed:
                self._conn = self._connect()
            try:
                with self._conn.transaction(), self._conn.cursor() as cursor:
                    cursor.execute("DELETE FROM chunks WHERE knowledge_id = %s", (knowledge_id,))
                    for record in records:
                        embedding = record["embedding"]
                        cursor.execute(
                            """
                            INSERT INTO chunks
                                (id, knowledge_id, file_id, chunk_index, content,
                                 filename, tokens, dim, embedding, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                            """,
                            (
                                uuid.uuid4().hex,
                                knowledge_id,
                                record["file_id"],
                                record["chunk_index"],
                                record["content"],
                                record.get("filename") or "未知文件",
                                record.get("tokens") or "",
                                len(embedding),
                                _to_pgvector(embedding),
                                now,
                            ),
                        )
            except psycopg.OperationalError:
                self._conn = None
                raise

    def count_chunks(self, knowledge_id: str) -> int:
        rows = self._execute(
            "SELECT COUNT(*) FROM chunks WHERE knowledge_id = %s", (knowledge_id,), fetch=True
        )
        return int(rows[0][0]) if rows else 0

    def delete_for_knowledge(self, knowledge_id: str) -> None:
        self._execute("DELETE FROM chunks WHERE knowledge_id = %s", (knowledge_id,))

    def delete_for_file(self, file_id: str, knowledge_id: str | None = None) -> None:
        if knowledge_id is None:
            self._execute("DELETE FROM chunks WHERE file_id = %s", (file_id,))
        else:
            self._execute(
                "DELETE FROM chunks WHERE knowledge_id = %s AND file_id = %s",
                (knowledge_id, file_id),
            )

    # ─── ranking primitives ────────────────────────────────

    def query_by_vector(
        self, knowledge_id: str, vector: list[float], limit: int
    ) -> list[dict[str, Any]]:
        if not vector:
            return []
        query_vec = _to_pgvector(vector)
        rows = self._execute(
            """
            SELECT id, file_id, filename, chunk_index, content,
                   1 - (embedding <=> %s::vector) AS score
            FROM chunks
            WHERE knowledge_id = %s AND dim = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_vec, knowledge_id, len(vector), query_vec, limit),
            fetch=True,
        )
        return [self._row_to_dict(row) for row in rows or []]

    def query_by_keywords(
        self, knowledge_id: str, text: str, limit: int
    ) -> list[dict[str, Any]]:
        # Reuse the shared CJK-bigram tokenizer so both index side (tokens
        # column) and query side agree, then let websearch_to_tsquery handle
        # quoting; OR semantics mirror the FTS5 match query.
        tokens = tokenize_for_bm25(text).split()
        if not tokens:
            return []
        seen: set[str] = set()
        unique = [token for token in tokens if not (token in seen or seen.add(token))][:32]
        ts_query = " OR ".join(unique)
        rows = self._execute(
            """
            SELECT id, file_id, filename, chunk_index, content,
                   ts_rank(tokens_tsv, websearch_to_tsquery('simple', %s)) AS score
            FROM chunks
            WHERE knowledge_id = %s
              AND tokens_tsv @@ websearch_to_tsquery('simple', %s)
            ORDER BY score DESC
            LIMIT %s
            """,
            (ts_query, knowledge_id, ts_query, limit),
            fetch=True,
        )
        return [self._row_to_dict(row) for row in rows or []]

    @staticmethod
    def _row_to_dict(row: tuple) -> dict[str, Any]:
        return {
            "id": row[0],
            "file_id": row[1],
            "filename": row[2],
            "chunk_index": row[3],
            "content": row[4],
            "score": float(row[5]),
        }
