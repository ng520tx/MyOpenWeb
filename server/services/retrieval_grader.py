"""Agentic retrieval self-correction: grade retrieved chunks, retry once if weak.

行业里的 Agentic RAG（Router → Grader → self-correction）核心是"检索完先评估，
不足再纠正"。这里做最小可用闭环：

1. Grader：一次 temperature=0 调用，让模型判断候选片段能否回答问题，
   输出 JSON {"sufficient": bool, "followup_query": "缺什么就检索什么"}
2. 不足时用 followup_query 重检索一轮（硬上限 1 次，防止延迟螺旋），
   两轮结果按 chunk_id 去重合并，二轮结果优先（针对缺口检索）
3. Grader 超时/输出脏格式 → 视为 sufficient，直接用首轮结果
   （与 rerank / query rewrite 同款降级哲学：增强环节绝不弄坏主链路）
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from server.schemas.config import ProviderConfig
from server.services.providers import create_chat_completion_text

logger = logging.getLogger(__name__)

# 不截断到低于常规 chunk_size（600），否则答案可能恰好被截掉，
# Grader 会"正确地"判定它看到的残缺资料不足，造成大量误触发。
MAX_CHUNK_CHARS = 700
MAX_FOLLOWUP_CHARS = 200

GRADER_INSTRUCTION = """你是检索质量评估器。判断【候选资料】中是否包含【用户问题】的答案信息。
判定标准（宽松）：只要任意一个片段包含能回答问题的关键信息（数值、步骤、名称、结论等），就算足够，不要求资料完整或详尽。
只输出一个 JSON 对象，不要任何解释：
- 资料中有答案：{"sufficient": true}
- 所有片段都与问题无关、确实找不到答案：{"sufficient": false, "followup_query": "换一种表述的补充检索查询"}

followup_query 必须换一种表述，禁止重复原问题：把口语换成企业文档里会出现的书面术语与关键词。
例：「新版本什么时候才能上线」→「发布窗口 发布时间 变更单」；「报警没人管会怎样」→「告警认领 升级 值班」。"""


def _parse_grader_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


async def grade_retrieval(
    config: ProviderConfig,
    model: str,
    query: str,
    chunks: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Return (sufficient, followup_query). Fail open: any error means sufficient."""
    if not chunks:
        return True, ""

    blocks = [
        f"[{index}] {chunk['content'][:MAX_CHUNK_CHARS]}"
        for index, chunk in enumerate(chunks, start=1)
    ]
    prompt = (
        f"【用户问题】{query.strip()}\n\n【候选资料】\n" + "\n\n".join(blocks)
    )

    try:
        raw = await create_chat_completion_text(
            config,
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "system_prompt": GRADER_INSTRUCTION,
                "temperature": 0.0,
                "max_tokens": 128,
                "stream": False,
            },
        )
    except Exception as exc:  # noqa: BLE001 - retrieval must survive grader failures
        logger.warning("retrieval grader failed, keeping first-pass results: %s", exc)
        return True, ""

    decision = _parse_grader_json(raw)
    if decision is None or not isinstance(decision.get("sufficient"), bool):
        logger.warning("retrieval grader returned malformed output, keeping first-pass results")
        return True, ""

    if decision["sufficient"]:
        return True, ""

    followup = str(decision.get("followup_query") or "").strip()
    if not followup or len(followup) > MAX_FOLLOWUP_CHARS:
        # 判了不足却给不出可用的补充查询，等于无法纠正，保持首轮。
        return True, ""
    if followup == query.strip():
        # 重复原查询的重检索只会得到一样的结果，没有纠正意义。
        return True, ""
    return False, followup


def merge_chunks(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Dedup by chunk_id. First-pass results are kept in full (they may already
    contain the answer even when the grader disagrees), follow-up results are
    appended into a slightly enlarged budget so corrections can actually land."""
    budget = top_k + max(2, top_k // 2)
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in [*first, *second]:
        chunk_id = chunk["chunk_id"]
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        merged.append(chunk)
    return merged[: max(1, budget)]
