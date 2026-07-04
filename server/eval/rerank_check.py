"""Verify the cross-encoder rerank stage loads and scores correctly."""
from __future__ import annotations

import os
import time

os.environ.setdefault("MYOPENWEB_DATA_DIR", "server/eval/.data")


def main() -> None:
    from sentence_transformers import CrossEncoder

    started = time.perf_counter()
    model = CrossEncoder("BAAI/bge-reranker-base")
    print(f"LOAD_OK {time.perf_counter() - started:.1f}s")

    pairs = [
        ("Redis 内存占用过高怎么排查", "执行 redis-cli --bigkeys 定位大 key，确认 used_memory。"),
        ("Redis 内存占用过高怎么排查", "MySQL 全量备份每天凌晨 2 点执行，保留 7 天。"),
    ]
    scores = model.predict(pairs)
    print("SCORES", [round(float(score), 3) for score in scores])
    assert scores[0] > scores[1], "relevant pair must outrank irrelevant pair"
    print("RERANK_CHECK_OK")


if __name__ == "__main__":
    main()
