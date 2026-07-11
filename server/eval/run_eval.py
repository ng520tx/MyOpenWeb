"""RAG retrieval quality eval harness.

Builds a sandboxed knowledge base from a source document, replays a QA dataset
against it, and reports Hit@K / MRR / latency across parameter combinations
(chunk_size x retrieval mode x rerank). Results feed the numbers quoted in the
resume/README.

Run inside the backend venv (Ollama with the embedding model must be running):

    MYOPENWEB_DATA_DIR=server/eval/.data ./.venv/bin/python -m server.eval.run_eval

Options:
    --docs examples/ops-manual.md,examples/api-reference.md,examples/faq-onboarding.md
    --dataset server/eval/dataset.jsonl
    --chunk-sizes 400,600,800
    --rerank auto|on|off           auto = include rerank rows when deps exist
    --out server/eval/results.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import statistics
import sys
import time
from pathlib import Path

# Sandbox all SQLite/file state before server modules are imported.
os.environ.setdefault("MYOPENWEB_DATA_DIR", "server/eval/.data")

from server.db import init_db  # noqa: E402
from server.repositories.files import create_file  # noqa: E402
from server.repositories.knowledge import bind_file, create_knowledge  # noqa: E402
from server.schemas.config import ProviderConfig  # noqa: E402
from server.services.rag import index_knowledge, query_knowledge  # noqa: E402
from server.services.rerank import rerank_available  # noqa: E402

EVAL_TOP_K = 8
HIT_LEVELS = (1, 4, 8)


def build_config() -> ProviderConfig:
    return ProviderConfig(
        provider_type=os.environ.get("EVAL_PROVIDER_TYPE", "ollama"),  # type: ignore[arg-type]
        provider_base_url=os.environ.get("EVAL_PROVIDER_BASE_URL", "http://localhost:11434/v1"),
        provider_api_key=os.environ.get("EVAL_PROVIDER_API_KEY", ""),
        embedding_model=os.environ.get("EVAL_EMBEDDING_MODEL", "bge-m3"),
        rerank_model=os.environ.get("EVAL_RERANK_MODEL", "BAAI/bge-reranker-base"),
    )


def load_dataset(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def is_relevant(chunk_content: str, expects: list[str]) -> bool:
    return any(expect in chunk_content for expect in expects)


async def eval_one_config(
    config: ProviderConfig,
    knowledge_id: str,
    dataset: list[dict],
    mode: str,
    rerank: bool,
) -> dict:
    hits = {k: 0 for k in HIT_LEVELS}
    reciprocal_ranks: list[float] = []
    latencies: list[float] = []

    for item in dataset:
        started = time.perf_counter()
        chunks = await query_knowledge(
            config,
            config.embedding_model,
            knowledge_id,
            item["query"],
            top_k=EVAL_TOP_K,
            mode=mode,
            rerank=rerank,
        )
        latencies.append((time.perf_counter() - started) * 1000)

        first_hit_rank = None
        for rank, chunk in enumerate(chunks, start=1):
            if is_relevant(chunk["content"], item["expect"]):
                first_hit_rank = rank
                break

        reciprocal_ranks.append(1.0 / first_hit_rank if first_hit_rank else 0.0)
        for k in HIT_LEVELS:
            if first_hit_rank is not None and first_hit_rank <= k:
                hits[k] += 1

    total = len(dataset)
    latencies_sorted = sorted(latencies)
    p95_index = max(0, min(total - 1, int(round(total * 0.95)) - 1))
    return {
        "mode": mode,
        "rerank": rerank,
        **{f"hit@{k}": hits[k] / total for k in HIT_LEVELS},
        "mrr": statistics.mean(reciprocal_ranks),
        "avg_ms": statistics.mean(latencies),
        "p95_ms": latencies_sorted[p95_index],
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="MyOpenWeb RAG retrieval eval")
    parser.add_argument(
        "--docs",
        default="examples/ops-manual.md,examples/api-reference.md,examples/faq-onboarding.md",
        help="comma-separated corpus documents",
    )
    parser.add_argument("--dataset", default="server/eval/dataset.jsonl")
    parser.add_argument("--chunk-sizes", default="400,600,800")
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--rerank", choices=["auto", "on", "off"], default="auto")
    parser.add_argument("--out", default="server/eval/results.md")
    parser.add_argument("--keep-data", action="store_true", help="reuse the sandbox data dir")
    args = parser.parse_args()

    data_dir = Path(os.environ["MYOPENWEB_DATA_DIR"])
    if not args.keep_data and data_dir.exists():
        shutil.rmtree(data_dir)
    init_db()

    doc_paths = [Path(item.strip()) for item in args.docs.split(",") if item.strip()]
    config = build_config()
    dataset = load_dataset(Path(args.dataset))
    chunk_sizes = [int(size) for size in args.chunk_sizes.split(",") if size.strip()]

    if args.rerank == "on" and not rerank_available():
        print("[warn] --rerank on 但未安装 sentence-transformers，跳过 rerank 行", file=sys.stderr)
    include_rerank = (
        args.rerank != "off" and rerank_available()
    )

    knowledge = create_knowledge("eval-corpus", "retrieval eval sandbox")
    total_chars = 0
    for doc_path in doc_paths:
        text = doc_path.read_text(encoding="utf-8")
        total_chars += len(text)
        file_record = create_file(
            filename=doc_path.name,
            raw=text.encode("utf-8"),
            mime_type="text/markdown",
            text_content=text,
        )
        bind_file(knowledge.id, file_record.id)

    print(f"数据集：{len(dataset)} 条 | 语料：{len(doc_paths)} 份文档（共 {total_chars} 字符）")
    print(f"embedding：{config.embedding_model} | rerank：{'启用对照' if include_rerank else '未参与'}")

    results: list[dict] = []
    for chunk_size in chunk_sizes:
        index_info = await index_knowledge(
            config, config.embedding_model, knowledge.id, chunk_size=chunk_size, overlap=args.overlap
        )
        print(f"\nchunk_size={chunk_size} overlap={args.overlap} → {index_info['chunks']} chunks")

        combos: list[tuple[str, bool]] = [("vector", False), ("hybrid", False)]
        if include_rerank:
            combos.append(("hybrid", True))

        if include_rerank:
            # Warm up the cross-encoder so model load time doesn't skew latency.
            await query_knowledge(
                config, config.embedding_model, knowledge.id, dataset[0]["query"],
                top_k=2, mode="hybrid", rerank=True,
            )

        for mode, rerank in combos:
            row = await eval_one_config(config, knowledge.id, dataset, mode, rerank)
            row["chunk_size"] = chunk_size
            row["chunks"] = index_info["chunks"]
            results.append(row)
            print(
                f"  {mode:6s}{' +rerank' if rerank else '        '}"
                f"  Hit@1={row['hit@1']:.2f}  Hit@4={row['hit@4']:.2f}  Hit@8={row['hit@8']:.2f}"
                f"  MRR={row['mrr']:.3f}  avg={row['avg_ms']:.0f}ms  p95={row['p95_ms']:.0f}ms"
            )

    write_report(Path(args.out), args, config, dataset, doc_paths, results)
    print(f"\n结果已写入 {args.out}")
    return 0


def write_report(
    out_path: Path,
    args: argparse.Namespace,
    config: ProviderConfig,
    dataset: list[dict],
    doc_paths: list[Path],
    results: list[dict],
) -> None:
    doc_names = ", ".join(f"`{path.name}`" for path in doc_paths)
    lines = [
        "# RAG 检索质量评测报告",
        "",
        f"- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 语料：{doc_names}；数据集：`{args.dataset}`（{len(dataset)} 条 QA）",
        f"- embedding 模型：`{config.embedding_model}`；overlap：{args.overlap}",
        f"- 评测方式：每条 QA 检索 top{EVAL_TOP_K}，命中判定为片段包含期望关键串（Hit@K），"
        "MRR 取首个命中片段排名倒数的平均值；耗时含查询向量化，为端到端检索延迟。",
        "",
        "| chunk_size | 分块数 | 检索模式 | Hit@1 | Hit@4 | Hit@8 | MRR | 平均耗时 | P95 耗时 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in results:
        mode_label = row["mode"] + ("+rerank" if row["rerank"] else "")
        lines.append(
            f"| {row['chunk_size']} | {row['chunks']} | {mode_label} "
            f"| {row['hit@1']:.2f} | {row['hit@4']:.2f} | {row['hit@8']:.2f} "
            f"| {row['mrr']:.3f} | {row['avg_ms']:.0f} ms | {row['p95_ms']:.0f} ms |"
        )
    lines += [
        "",
        "说明：",
        "",
        "- Hit@K 为宽松召回率（gold 以关键串匹配近似），横向对比不同参数与检索模式仍然有效；"
        "严格人工标注集可在数据规模上来后替换 `is_relevant` 判定。",
        "- rerank 行的耗时为 CPU 推理（CrossEncoder 对候选池逐对打分）。CPU 场景适合质量优先/离线链路；"
        "在线低延迟场景建议 GPU、ONNX 量化或缩小候选池。",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
