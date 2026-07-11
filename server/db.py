from __future__ import annotations

import contextlib
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
# MYOPENWEB_DATA_DIR lets Docker volumes and the eval harness relocate all
# persisted state (SQLite + uploaded files) away from the source tree.
DATA_DIR = (
    Path(os.environ["MYOPENWEB_DATA_DIR"]).resolve()
    if os.environ.get("MYOPENWEB_DATA_DIR")
    else ROOT_DIR / "data"
)
DB_PATH = DATA_DIR / "myopenweb.db"


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # SQLite ships with foreign keys OFF per connection; without this pragma
    # every ON DELETE CASCADE in the schema is silently ignored.
    conn.execute("PRAGMA foreign_keys = ON")
    # Ride out short writer contention (chat saves + agent_steps + re-index
    # can overlap) instead of failing fast with "database is locked".
    conn.execute("PRAGMA busy_timeout = 5000")
    # WAL lets readers proceed while a writer commits. Falls back to the
    # default journal on filesystems without shared-memory support
    # (e.g. WSL /mnt drvfs, some network mounts).
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                message_id TEXT,
                user_message_id TEXT,
                model TEXT NOT NULL,
                user_input TEXT NOT NULL,
                final_answer TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_steps (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                type TEXT NOT NULL,
                name TEXT,
                input_json TEXT,
                output_json TEXT,
                ok INTEGER NOT NULL DEFAULT 1,
                error TEXT,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS agent_steps_run_id_idx ON agent_steps(run_id, step_index);
            CREATE INDEX IF NOT EXISTS agent_runs_conversation_id_idx ON agent_runs(conversation_id, created_at);

            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'fact',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS memories_enabled_idx ON memories(enabled, updated_at);

            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                mime_type TEXT,
                size INTEGER NOT NULL DEFAULT 0,
                hash TEXT,
                text_content TEXT,
                meta_json TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS files_hash_idx ON files(hash);
            CREATE INDEX IF NOT EXISTS files_created_idx ON files(created_at);

            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS knowledge_file (
                knowledge_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (knowledge_id, file_id),
                FOREIGN KEY (knowledge_id) REFERENCES knowledge(id) ON DELETE CASCADE,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                knowledge_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (knowledge_id) REFERENCES knowledge(id) ON DELETE CASCADE,
                FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS chunks_knowledge_idx ON chunks(knowledge_id, chunk_index);
            CREATE INDEX IF NOT EXISTS knowledge_file_kid_idx ON knowledge_file(knowledge_id);
            """
        )
        conn.commit()

        _init_fts(conn)

        count = conn.execute("SELECT COUNT(*) AS count FROM app_config").fetchone()["count"]
        if count == 0:
            now = int(time.time() * 1000)
            # First-run seeds; PROVIDER_* / EMBEDDING_MODEL envs let Docker
            # point a fresh container at the right model service.
            defaults = {
                "provider_type": os.environ.get("PROVIDER_TYPE", "ollama"),
                "provider_base_url": os.environ.get(
                    "PROVIDER_BASE_URL", "http://localhost:11434/v1"
                ),
                "provider_api_key": os.environ.get("PROVIDER_API_KEY", ""),
                "embedding_model": os.environ.get("EMBEDDING_MODEL", "bge-m3"),
                "ocr_enabled": "0",
                "ocr_base_url": "http://localhost:8118",
                "ocr_mode": "auto",
                "retrieval_mode": "hybrid",
                "rerank_enabled": "0",
                "rerank_model": "BAAI/bge-reranker-base",
            }
            conn.executemany(
                "INSERT OR REPLACE INTO app_config (key, value, updated_at) VALUES (?, ?, ?)",
                [(key, value, now) for key, value in defaults.items()],
            )
            conn.commit()


def _init_fts(conn: sqlite3.Connection) -> None:
    """Create the FTS5 index over chunk contents used by BM25 retrieval.

    Tokenized text (CJK bigrams + latin words) is stored alongside the chunk id
    so hybrid retrieval can join back to the chunks table. When the local
    SQLite build lacks FTS5 the app still works in pure vector mode.
    """
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                knowledge_id UNINDEXED,
                tokens
            )
            """
        )
        conn.commit()
    except sqlite3.OperationalError:
        # SQLite compiled without FTS5; hybrid retrieval degrades to vector-only.
        pass


def fts_available() -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'chunks_fts'"
        ).fetchone()
    return row is not None


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
