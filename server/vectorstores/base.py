"""VectorStore protocol: the seam that lets retrieval swap storage engines.

Everything above this interface (RRF fusion, rerank, query rewrite, grader,
agent tools, MCP server) is backend-agnostic. Implementations own chunk
persistence plus the two primitive rankings that hybrid retrieval fuses:

- ``query_by_vector``  — cosine top-k over embeddings
- ``query_by_keywords`` — BM25-style keyword top-k over pre-tokenized text

Chunk records passed to :meth:`replace_chunks`::

    {
        "file_id": str,
        "filename": str,        # denormalized for backends without the files table
        "chunk_index": int,
        "content": str,
        "embedding": list[float],
        "tokens": str,          # space-joined tokens from services.tokenize
    }

Rows returned by both query methods::

    {"id", "file_id", "filename", "chunk_index", "content", "score"}
"""
from __future__ import annotations

from typing import Any, Protocol


class VectorStore(Protocol):
    """Storage backend for knowledge-base chunks and their embeddings."""

    backend: str

    def replace_chunks(self, knowledge_id: str, records: list[dict[str, Any]]) -> None:
        """Atomically swap all chunks of a knowledge base with a fresh set."""
        ...

    def count_chunks(self, knowledge_id: str) -> int:
        ...

    def delete_for_knowledge(self, knowledge_id: str) -> None:
        ...

    def delete_for_file(self, file_id: str, knowledge_id: str | None = None) -> None:
        """Drop chunks of one file — in a single knowledge base, or everywhere
        when ``knowledge_id`` is None (file deletion)."""
        ...

    def query_by_vector(
        self, knowledge_id: str, vector: list[float], limit: int
    ) -> list[dict[str, Any]]:
        """Top ``limit`` rows by cosine similarity (best first). Rows whose
        embedding dimension differs from the query vector are excluded, so a
        stale index (embedding model changed) yields an empty result."""
        ...

    def query_by_keywords(
        self, knowledge_id: str, text: str, limit: int
    ) -> list[dict[str, Any]]:
        """Top ``limit`` rows by keyword relevance (best first). Backends may
        return an empty list when full-text search is unavailable — hybrid
        retrieval then degrades to pure vector ranking."""
        ...
