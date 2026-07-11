"""Agentic retrieval self-correction eval: single-pass vs. grader + retry.

For each QA case we retrieve top_k once (baseline), then run the agentic
pipeline (grade → bounded follow-up retrieval → merge) and compare Hit@K /
MRR / latency. This quantifies what the self-correction loop buys and what it
costs (one extra LLM call when triggered).

Run inside the backend venv (Ollama must serve chat + embedding models):

    MYOPENWEB_DATA_DIR=server/eval/.data ./.venv/bin/python -m server.eval.run_agentic_eval

Options:
    --model qwen2.5:3b             chat model used by the grader
    --dataset server/eval/dataset.jsonl
    --top-k 4                      production-like context budget
    --out server/eval/results-agentic.md
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
from server.services.rag import index_knowledge, query_knowledge  # noqa: E402
from server.services.retrieval_grader import grade_retrieval, merge_chunks  # noqa: E402

HIT_LEVELS = (1, 4)
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


def summarize(ranks: list[int | None], latencies: list[float]) -> dict:
    total = len(ranks)
    return {
        **{
            f"hit@{k}": sum(1 for r in ranks if r is not None and r <= k) / total
            for k in HIT_LEVELS
        },
        "mrr": statistics.mean(1.0 / r if r else 0.0 for r in ranks),
        "avg_ms": statistics.mean(latencies),
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="MyOpenWeb agentic retrieval eval")
    parser.add_argument("--docs", default=DEFAULT_DOCS)
    parser.add_argument("--dataset", default="server/eval/dataset.jsonl")
    parser.add_argument("--model", default=os.environ.get("EVAL_CHAT_MODEL", "qwen2.5:3b"))
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--chunk-size", type=int, default=600)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--out", default="server/eval/results-agentic.md")
    args = parser.parse_args()

    data_dir = Path(os.environ["MYOPENWEB_DATA_DIR"])
    if data_dir.exists():
        shutil.rmtree(data_dir)
    init_db()

    config = build_config()
    dataset = load_dataset(Path(args.dataset))

    knowledge = create_knowledge("agentic-eval", "agentic retrieval eval sandbox")
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
    print(
        f"语料索引完成：{index_info['chunks']} chunks | 用例：{len(dataset)} 条 "
        f"| top_k={args.top_k} | Grader 模型：{args.model}"
    )

    base_ranks: list[int | None] = []
    agentic_ranks: list[int | None] = []
    base_latencies: list[float] = []
    agentic_latencies: list[float] = []
    corrections = 0  # grader 判不足且触发了重检索的次数
    saved_cases: list[dict] = []  # baseline 未命中而 agentic 命中的用例

    for item in dataset:
        query = item["query"]

        started = time.perf_counter()
        first = await query_knowledge(
            config, config.embedding_model, knowledge.id, query, top_k=args.top_k
        )
        base_latencies.append((time.perf_counter() - started) * 1000)
        base_rank = first_hit_rank(first, item["expect"])
        base_ranks.append(base_rank)

        started = time.perf_counter()
        chunks = first
        sufficient, followup = await grade_retrieval(config, args.model, query, chunks)
        if not sufficient:
            corrections += 1
            extra = await query_knowledge(
                config, config.embedding_model, knowledge.id, followup,
                top_k=max(args.top_k, 4),
            )
            if extra:
                chunks = merge_chunks(chunks, extra, args.top_k)
        # baseline 检索耗时不重复计入 agentic 侧（复用了首轮结果），
        # 这里补上首轮耗时得到端到端延迟。
        agentic_latencies.append(
            (time.perf_counter() - started) * 1000 + base_latencies[-1]
        )
        agentic_rank = first_hit_rank(chunks, item["expect"])
        agentic_ranks.append(agentic_rank)

        marker = ""
        if base_rank is None and agentic_rank is not None:
            marker = " ← 纠错救回"
            saved_cases.append({"query": query, "followup": followup})
        elif not sufficient:
            marker = " (触发重检索)"
        print(f"  base={base_rank or '-'} agentic={agentic_rank or '-'}{marker}  「{query}」")

    base_stats = summarize(base_ranks, base_latencies)
    agentic_stats = summarize(agentic_ranks, agentic_latencies)
    print(
        f"\n单轮检索   Hit@1={base_stats['hit@1']:.2f}  Hit@4={base_stats['hit@4']:.2f}"
        f"  MRR={base_stats['mrr']:.3f}  avg={base_stats['avg_ms']:.0f}ms"
        f"\n自纠错检索 Hit@1={agentic_stats['hit@1']:.2f}  Hit@4={agentic_stats['hit@4']:.2f}"
        f"  MRR={agentic_stats['mrr']:.3f}  avg={agentic_stats['avg_ms']:.0f}ms"
        f"\nGrader 触发重检索：{corrections}/{len(dataset)} 次；救回未命中：{len(saved_cases)} 条"
    )

    write_report(
        Path(args.out), args, dataset, base_stats, agentic_stats, corrections, saved_cases
    )
    print(f"结果已写入 {args.out}")
    return 0


def write_report(
    out_path: Path,
    args: argparse.Namespace,
    dataset: list[dict],
    base_stats: dict,
    agentic_stats: dict,
    corrections: int,
    saved_cases: list[dict],
) -> None:
    lines = [
        "# Agentic 检索自纠错评测报告",
        "",
        f"- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 用例：`{args.dataset}`（{len(dataset)} 条）；top_k={args.top_k}；chunk_size={args.chunk_size}；检索模式：hybrid",
        f"- Grader 模型：`{args.model}`（temperature=0，判断候选片段能否回答问题；不足时输出补充查询并重检索一轮，上限 1 次）",
        f"- Grader 触发重检索：{corrections}/{len(dataset)} 次；救回 baseline 未命中用例：{len(saved_cases)} 条",
        "",
        "| 指标 | 单轮检索（关） | 自纠错检索（开） |",
        "|---|---|---|",
        *[
            f"| {label} | {base_stats[key]:.2f} | {agentic_stats[key]:.2f} |"
            for label, key in (("Hit@1", "hit@1"), ("Hit@4", "hit@4"), ("MRR", "mrr"))
        ],
        f"| 平均端到端延迟 | {base_stats['avg_ms']:.0f} ms | {agentic_stats['avg_ms']:.0f} ms |",
        "",
    ]
    if saved_cases:
        lines += [
            "## 纠错救回的用例",
            "",
            "| 问题 | Grader 生成的补充查询 |",
            "|---|---|",
            *[f"| {case['query']} | {case['followup']} |" for case in saved_cases],
            "",
        ]
    lines += [
        "说明：自纠错的收益集中在首轮检索未覆盖答案的问题上；对首轮已命中的问题，Grader 判定足够后直接放行，"
        "不改变结果。延迟增量 = Grader 一次小请求 +（触发时）一轮重检索；Grader 失败或输出脏格式时自动沿用首轮结果。",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
