from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "myopenweb.db"


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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

        count = conn.execute("SELECT COUNT(*) AS count FROM app_config").fetchone()["count"]
        if count == 0:
            now = int(time.time() * 1000)
            defaults = {
                "provider_type": "ollama",
                "provider_base_url": "http://localhost:11434/v1",
                "provider_api_key": "",
                "embedding_model": "bge-m3",
                "ocr_enabled": "0",
                "ocr_base_url": "http://localhost:8118",
                "ocr_mode": "auto",
            }
            conn.executemany(
                "INSERT OR REPLACE INTO app_config (key, value, updated_at) VALUES (?, ?, ?)",
                [(key, value, now) for key, value in defaults.items()],
            )
            conn.commit()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
