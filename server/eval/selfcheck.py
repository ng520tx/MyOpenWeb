"""Quick environment self-check for the eval harness (FTS5, imports, tokenizer)."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("MYOPENWEB_DATA_DIR", "server/eval/.data")


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
    print("FTS5_OK", sqlite3.sqlite_version)

    import server.main  # noqa: F401

    print("IMPORT_OK")

    from server.services.tokenize import build_match_query, tokenize_for_bm25

    sample = tokenize_for_bm25("HikariCP 连接池耗尽，执行 SHOW PROCESSLIST 检查 MySQL")
    print("TOKENIZE_OK", sample)
    print("MATCH_OK", build_match_query("Redis 内存占用过高怎么办"))

    from server.services.rerank import rerank_available

    print("RERANK_AVAILABLE", rerank_available())


if __name__ == "__main__":
    main()
