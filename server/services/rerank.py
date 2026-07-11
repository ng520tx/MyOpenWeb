"""Optional cross-encoder rerank stage (bge-reranker family).

The heavy dependencies (sentence-transformers + torch) are imported lazily and
only when rerank is enabled in the config. When they are missing or the model
fails to load, callers receive ``None`` and fall back to the fused retrieval
order, so the core RAG path never hard-depends on torch.

Install (separate from the base requirements to keep the backend light):
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install sentence-transformers
Domestic mirror for the model download: set HF_ENDPOINT=https://hf-mirror.com
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_model_cache: dict[str, Any] = {}
# Negative cache: once a model fails to load (missing deps, no network for the
# download), stop retrying on every request — retries would add tens of
# seconds of latency to each retrieval.
_failed_models: set[str] = set()
_warned = False


def _load_model(model_name: str):
    global _warned
    if model_name in _failed_models:
        return None
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        _failed_models.add(model_name)
        if not _warned:
            logger.warning(
                "rerank 已开启但未安装 sentence-transformers，回退为不重排。"
                "安装：pip install torch --index-url https://download.pytorch.org/whl/cpu sentence-transformers"
            )
            _warned = True
        return None

    if model_name not in _model_cache:
        try:
            _model_cache[model_name] = CrossEncoder(model_name)
        except Exception as exc:  # noqa: BLE001 - model download/load can fail many ways
            _failed_models.add(model_name)
            logger.warning("rerank 模型 %s 加载失败（%s），回退为不重排", model_name, exc)
            return None
    return _model_cache[model_name]


async def rerank_chunks(
    model_name: str, query: str, chunks: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """Re-order candidate chunks by cross-encoder relevance.

    Returns a new list with ``score`` replaced by the rerank score (higher is
    better), or ``None`` when reranking is unavailable so the caller keeps the
    original order.
    """
    if not chunks:
        return []

    model = await asyncio.to_thread(_load_model, model_name)
    if model is None:
        return None

    pairs = [(query, chunk["content"]) for chunk in chunks]
    try:
        scores = await asyncio.to_thread(model.predict, pairs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rerank 推理失败（%s），回退为不重排", exc)
        return None

    order = sorted(range(len(chunks)), key=lambda i: -float(scores[i]))
    return [{**chunks[i], "score": float(scores[i])} for i in order]


def rerank_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True
