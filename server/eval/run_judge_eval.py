"""LLM-as-judge answer quality eval for the RAG pipeline.

For each sampled QA case: retrieve → build the grounded system prompt →
generate an answer with the chat model → have a (different) judge model score
the answer on two axes:

- faithfulness: does the answer stay inside the retrieved context (no made-up
  facts)? A clean refusal on empty retrieval counts as faithful.
- relevancy: does the answer actually address the question?

This is a lightweight, dependency-free take on what RAGAS calls
faithfulness / answer relevancy; swap in a stronger judge model in production.

    MYOPENWEB_DATA_DIR=server/eval/.data ./.venv/bin/python -m server.eval.run_judge_eval

Options:
    --gen-model qwen2.5:3b     answering model
    --judge-model qwen3.5:4b   scoring model (prefer a different/stronger one)
    --limit 12                 number of QA cases sampled from dataset.jsonl
    --out server/eval/results-judge.md
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import json
import os
import re
import shutil
import statistics
import time
from pathlib import Path

os.environ.setdefault("MYOPENWEB_DATA_DIR", "server/eval/.data")

from server.db import init_db  # noqa: E402
from server.repositories.files import create_file  # noqa: E402
from server.repositories.knowledge import bind_file, create_knowledge  # noqa: E402
from server.schemas.config import ProviderConfig  # noqa: E402
from server.services.providers import create_chat_completion_text  # noqa: E402
from server.services.rag import (  # noqa: E402
    build_no_context_prompt,
    build_rag_system_prompt,
    index_knowledge,
    query_knowledge,
)

DEFAULT_DOCS = "examples/ops-manual.md,examples/api-reference.md,examples/faq-onboarding.md"

FAITHFULNESS_PROMPT = """你是严格的 RAG 评测员。请判断【回答】是否忠实于【参考资料】：
- 5：完全基于参考资料，或在资料未命中时明确回答"知识库中没有找到相关信息"（拒答也算忠实）。
- 3：主体基于资料，但夹带了少量资料以外的内容。
- 1：大量编造资料中不存在的信息，或与资料矛盾。
只输出一个 JSON 对象：{"score": 1到5的整数, "reason": "一句话理由"}"""

RELEVANCY_PROMPT = """你是严格的问答评测员。请判断【回答】是否切中【问题】：
- 5：直接、完整地回答了问题。
- 3：部分回答，遗漏关键信息或绕圈子。
- 1：答非所问。
只输出一个 JSON 对象：{"score": 1到5的整数, "reason": "一句话理由"}"""


def build_config() -> ProviderConfig:
    return ProviderConfig(
        provider_type=os.environ.get("EVAL_PROVIDER_TYPE", "ollama"),  # type: ignore[arg-type]
        provider_base_url=os.environ.get("EVAL_PROVIDER_BASE_URL", "http://localhost:11434/v1"),
        provider_api_key=os.environ.get("EVAL_PROVIDER_API_KEY", ""),
        embedding_model=os.environ.get("EVAL_EMBEDDING_MODEL", "bge-m3"),
    )


def load_dataset(path: Path, limit: int) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    # Deterministic spread across the corpus instead of the first N.
    step = max(1, len(rows) // limit)
    return rows[::step][:limit]


def parse_score(raw: str) -> tuple[int | None, str]:
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if match:
        text = match.group(0)
        data = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Some judges emit Python-dict style single quotes.
            try:
                data = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                data = None
        if isinstance(data, dict):
            try:
                score = int(data.get("score", 0))
            except (TypeError, ValueError):
                score = 0
            if 1 <= score <= 5:
                return score, str(data.get("reason", ""))[:120]
    return None, raw.strip()[:120]


async def judge(config: ProviderConfig, model: str, instruction: str, body: str) -> tuple[int | None, str]:
    raw = await create_chat_completion_text(
        config,
        {
            "model": model,
            "messages": [{"role": "user", "content": body}],
            "system_prompt": instruction,
            "temperature": 0.0,
            "max_tokens": 200,
            "stream": False,
        },
    )
    return parse_score(raw)


async def main() -> int:
    parser = argparse.ArgumentParser(description="MyOpenWeb LLM-as-judge answer eval")
    parser.add_argument("--docs", default=DEFAULT_DOCS)
    parser.add_argument("--dataset", default="server/eval/dataset.jsonl")
    parser.add_argument("--gen-model", default=os.environ.get("EVAL_CHAT_MODEL", "qwen2.5:3b"))
    parser.add_argument("--judge-model", default=os.environ.get("EVAL_JUDGE_MODEL", "qwen3.5:4b"))
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--out", default="server/eval/results-judge.md")
    args = parser.parse_args()

    data_dir = Path(os.environ["MYOPENWEB_DATA_DIR"])
    if data_dir.exists():
        shutil.rmtree(data_dir)
    init_db()

    config = build_config()
    dataset = load_dataset(Path(args.dataset), args.limit)

    knowledge = create_knowledge("judge-eval", "answer quality eval sandbox")
    for doc in [Path(item.strip()) for item in args.docs.split(",") if item.strip()]:
        text = doc.read_text(encoding="utf-8")
        record = create_file(
            filename=doc.name, raw=text.encode("utf-8"),
            mime_type="text/markdown", text_content=text,
        )
        bind_file(knowledge.id, record.id)
    info = await index_knowledge(config, config.embedding_model, knowledge.id)
    print(
        f"语料索引完成：{info['chunks']} chunks | 用例：{len(dataset)} 条"
        f" | 生成：{args.gen_model} | 评审：{args.judge_model}"
    )

    rows: list[dict] = []
    for item in dataset:
        chunks = await query_knowledge(
            config, config.embedding_model, knowledge.id, item["query"], top_k=args.top_k
        )
        context = "\n\n".join(f"[{i}] {c['content']}" for i, c in enumerate(chunks, start=1)) or "（未检索到资料）"
        system_prompt = (
            build_rag_system_prompt(None, chunks) if chunks else build_no_context_prompt(None)
        )
        answer = await create_chat_completion_text(
            config,
            {
                "model": args.gen_model,
                "messages": [{"role": "user", "content": item["query"]}],
                "system_prompt": system_prompt,
                "temperature": 0.2,
                "max_tokens": 600,
                "stream": False,
            },
        )

        judge_body = f"【问题】{item['query']}\n\n【参考资料】\n{context}\n\n【回答】\n{answer}"
        faith_score, faith_reason = await judge(config, args.judge_model, FAITHFULNESS_PROMPT, judge_body)
        rel_score, rel_reason = await judge(config, args.judge_model, RELEVANCY_PROMPT, judge_body)

        rows.append(
            {
                "query": item["query"],
                "answer": answer,
                "faithfulness": faith_score,
                "faith_reason": faith_reason,
                "relevancy": rel_score,
                "rel_reason": rel_reason,
            }
        )
        print(
            f"  faith={faith_score or '-'} rel={rel_score or '-'}  {item['query'][:36]}"
        )

    faith_scores = [row["faithfulness"] for row in rows if row["faithfulness"]]
    rel_scores = [row["relevancy"] for row in rows if row["relevancy"]]
    print(
        f"\nfaithfulness 平均 {statistics.mean(faith_scores):.2f}/5"
        f" | relevancy 平均 {statistics.mean(rel_scores):.2f}/5"
        f"（有效评分 {len(faith_scores)}/{len(rows)}）"
    )

    write_report(Path(args.out), args, rows, faith_scores, rel_scores)
    print(f"结果已写入 {args.out}")
    return 0


def write_report(
    out_path: Path,
    args: argparse.Namespace,
    rows: list[dict],
    faith_scores: list[int],
    rel_scores: list[int],
) -> None:
    lines = [
        "# RAG 生成质量评测报告（LLM-as-judge）",
        "",
        f"- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 抽样：`{args.dataset}` 等距抽 {len(rows)} 条；top_k={args.top_k}；检索模式 hybrid",
        f"- 生成模型：`{args.gen_model}`；评审模型：`{args.judge_model}`（生成与评审分离，降低自评偏好）",
        "- 评分维度对应 RAGAS 的 faithfulness / answer relevancy，采用零依赖自研实现：",
        "  评审模型对「问题 + 检索资料 + 回答」按 1–5 打分，拒答（资料未命中时明确说没找到）计为忠实。",
        "",
        "| 指标 | 平均分（1–5） | 有效评分 |",
        "|---|---|---|",
        f"| Faithfulness（忠实度） | {statistics.mean(faith_scores):.2f} | {len(faith_scores)}/{len(rows)} |",
        f"| Answer Relevancy（相关性） | {statistics.mean(rel_scores):.2f} | {len(rel_scores)}/{len(rows)} |",
        "",
        "## 逐条明细",
        "",
        "| 问题 | Faith | Rel | 评审理由（忠实度） |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['query'][:40]} | {row['faithfulness'] or '-'} | {row['relevancy'] or '-'} "
            f"| {row['faith_reason'][:60]} |"
        )
    lines += [
        "",
        "局限与生产建议：小模型互评仍有噪声，样本量有限；生产环境建议用更强的评审模型（GPT-4o/Claude 级）、",
        "扩大样本、并对低分样例做人工复核回归。本报告用于演示评测方法论与量化意识。",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
