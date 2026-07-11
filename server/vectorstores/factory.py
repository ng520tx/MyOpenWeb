"""Backend selection: deploy-time decision via environment variables.

MYOPENWEB_VECTOR_BACKEND=sqlite    (default; zero extra services)
MYOPENWEB_VECTOR_BACKEND=pgvector  + MYOPENWEB_PG_DSN=postgresql://user:pass@host:5432/db
"""
from __future__ import annotations

import os

from server.vectorstores.base import VectorStore

_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        backend = os.environ.get("MYOPENWEB_VECTOR_BACKEND", "sqlite").strip().lower()
        if backend == "pgvector":
            dsn = os.environ.get("MYOPENWEB_PG_DSN", "").strip()
            if not dsn:
                raise RuntimeError(
                    "MYOPENWEB_VECTOR_BACKEND=pgvector 需要同时设置 MYOPENWEB_PG_DSN"
                )
            from server.vectorstores.pgvector_store import PgVectorStore

            _store = PgVectorStore(dsn)
        elif backend == "sqlite":
            from server.vectorstores.sqlite_store import SqliteVectorStore

            _store = SqliteVectorStore()
        else:
            raise RuntimeError(f"未知的向量后端：{backend}（支持 sqlite / pgvector）")
    return _store


def reset_vector_store() -> None:
    """Test hook: drop the singleton so the next call re-reads the env."""
    global _store
    _store = None
