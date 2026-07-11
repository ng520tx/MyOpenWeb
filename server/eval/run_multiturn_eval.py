"""Multi-turn retrieval eval: raw follow-up query vs. LLM-rewritten query.

Each case carries conversation history plus a pronoun-laden follow-up
("它的端口是多少"). We retrieve twice — once with the raw follow-up text and
once with the rewritten self-contained query — and compare Hit@K / MRR.

Run inside the backend venv (Ollama must serve both the chat model used for
rewriting and the embedding model):

    MYOPENWEB_DATA_DIR=server/eval/.data ./.venv/bin/python -m server.eval.run_multiturn_eval

Options:
    --model qwen2.5:3b             chat model used by the rewriter
    --dataset server/eval/multiturn.jsonl
    --chunk-size 600
    --out server/eval/results-multiturn.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import statistics
import time
from pathlib import Path

os.environ.setdefault("MYOPENWEB_DATA_DIR", "server/eval/.data")

from server.db import init_db  # noqa: E402
from server.repositories.files import create_file  # noqa: E402
from server.repositories.knowledge import bind_file, create_knowledge  # noqa: E402
from server.schemas.config import ProviderConfig  # noqa: E402
from server.services.query_rewrite import rewrite_query  # noqa: E402
from server.services.rag import index_knowledge, query_knowledge  # noqa: E402

EVAL_TOP_K = 8
HIT_LEVELS = (1, 4, 8)
DEFAULT_DOCS = "examples/ops-manual.md,examples/api-reference.md,examples/faq-onboarding.md"


def build_config() -> ProviderConfig:
    return ProviderConfig(
        provider_type=os.environ.get("EVAL_PROVIDER_TYPE", "ollama"),  # type: ignore[arg-type]
        provider_base_url=os.environ.get("EVAL_PROVIDER_BASE_URL", "http://localhost:11434/v1"),
        provider_api_key=os.environ.get("EVAL_PROVIDER_API_KEY", ""),
        embedding_model=os.environ.get("EVAL_EMBEDDING_MODEL", "bge-m3"),
    )


def load_dataset(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def first_hit_rank(chunks: list[dict], expects: list[str]) -> int | None:
    for rank, chunk in enumerate(chunks, start=1):
        if any(expect in chunk["content"] for expect in expects):
            return rank
    return None


def summarize(ranks: list[int | None]) -> dict:
    total = len(ranks)
    return {
        **{
            f"hit@{k}": sum(1 for r in ranks if r is not None and r <= k) / total
            for k in HIT_LEVELS
        },
        "mrr": statistics.mean(1.0 / r if r else 0.0 for r in ranks),
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="MyOpenWeb multi-turn rewrite eval")
    parser.add_argument("--docs", default=DEFAULT_DOCS)
    parser.add_argument("--dataset", default="server/eval/multiturn.jsonl")
    parser.add_argument("--model", default=os.environ.get("EVAL_CHAT_MODEL", "qwen2.5:3b"))
    parser.add_argument("--chunk-size", type=int, default=600)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--out", default="server/eval/results-multiturn.md")
    args = parser.parse_args()

    data_dir = Path(os.environ["MYOPENWEB_DATA_DIR"])
    if data_dir.exists():
        shutil.rmtree(data_dir)
    init_db()

    config = build_config()
    dataset = load_dataset(Path(args.dataset))

    knowledge = create_knowledge("multiturn-eval", "multi-turn rewrite eval sandbox")
    for doc in [Path(item.strip()) for item in args.docs.split(",") if item.strip()]:
        text = doc.read_text(encoding="utf-8")
        record = create_file(
            filename=doc.name, raw=text.encode("utf-8"),
            mime_type="text/markdown", text_content=text,
        )
        bind_file(knowledge.id, record.id)
    index_info = await index_knowledge(
        config, config.embedding_model, knowledge.id,
        chunk_size=args.chunk_size, overlap=args.overlap,
    )
    print(f"语料索引完成：{index_info['chunks']} chunks | 用例：{len(dataset)} 条 | 改写模型：{args.model}")

    raw_ranks: list[int | None] = []
    rewritten_ranks: list[int | None] = []
    rows: list[dict] = []

    for item in dataset:
        raw_query = item["query"]
        payload = {
            "model": args.model,
            "messages": [*item["history"], {"role": "user", "content": raw_query}],
        }
        rewritten = await rewrite_query(config, payload, raw_query)

        raw_chunks = await query_knowledge(
            config, config.embedding_model, knowledge.id, raw_query, top_k=EVAL_TOP_K
        )
        rewritten_chunks = await query_knowledge(
            config, config.embedding_model, knowledge.id, rewritten, top_k=EVAL_TOP_K
        )

        raw_rank = first_hit_rank(raw_chunks, item["expect"])
        rewritten_rank = first_hit_rank(rewritten_chunks, item["expect"])
        raw_ranks.append(raw_rank)
        rewritten_ranks.append(rewritten_rank)
        rows.append(
            {
                "query": raw_query,
                "rewritten": rewritten,
                "raw_rank": raw_rank,
                "rewritten_rank": rewritten_rank,
            }
        )
        print(
            f"  原文命中排名={raw_rank or '-'} | 改写后={rewritten_rank or '-'}"
            f"  「{raw_query}」→「{rewritten}」"
        )

    raw_stats = summarize(raw_ranks)
    rewritten_stats = summarize(rewritten_ranks)
    print(
        f"\n原始追问   Hit@1={raw_stats['hit@1']:.2f}  Hit@4={raw_stats['hit@4']:.2f}  MRR={raw_stats['mrr']:.3f}"
        f"\n改写后检索 Hit@1={rewritten_stats['hit@1']:.2f}  Hit@4={rewritten_stats['hit@4']:.2f}  MRR={rewritten_stats['mrr']:.3f}"
    )

    write_report(Path(args.out), args, dataset, rows, raw_stats, rewritten_stats)
    print(f"结果已写入 {args.out}")
    return 0


def write_report(
    out_path: Path,
    args: argparse.Namespace,
    dataset: list[dict],
    rows: list[dict],
    raw_stats: dict,
    rewritten_stats: dict,
) -> None:
    lines = [
        "# 多轮对话检索改写评测报告",
        "",
        f"- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 用例：`{args.dataset}`（{len(dataset)} 条多轮指代追问）；chunk_size={args.chunk_size}；检索模式：hybrid",
        f"- 改写模型：`{args.model}`；对照方式：同一条追问分别用原文与改写后查询检索，比较首个命中排名。",
        "",
        "| 指标 | 原始追问 | 改写后 |",
        "|---|---|---|",
        *[
            f"| {label} | {raw_stats[key]:.2f} | {rewritten_stats[key]:.2f} |"
            for label, key in (
                ("Hit@1", "hit@1"),
                ("Hit@4", "hit@4"),
                ("Hit@8", "hit@8"),
                ("MRR", "mrr"),
            )
        ],
        "",
        "## 逐条对照",
        "",
        "| 追问 | 改写结果 | 原文命中排名 | 改写后排名 |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['query']} | {row['rewritten']} "
            f"| {row['raw_rank'] or '未命中'} | {row['rewritten_rank'] or '未命中'} |"
        )
    lines += [
        "",
        "说明：多轮追问常见代词指代与主语省略（“它的端口”），原文直接检索时 BM25 与向量都缺少可区分关键词；"
        "改写阶段用对话历史补全主语后再检索。改写失败时自动回退原文，检索链路不受影响。",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
