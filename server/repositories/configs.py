from __future__ import annotations

import time

from server.db import get_db
from server.schemas.config import ProviderConfig


def mask_provider_config(config: ProviderConfig) -> ProviderConfig:
    """Presentation copy for API responses: never leak the stored key.

    Any client on the LAN can call GET /api/config/provider, so the key is
    reduced to a ``***xxxx`` fingerprint (enough for the user to recognise
    which key is configured).
    """
    key = config.provider_api_key
    if not key:
        return config
    masked = f"***{key[-4:]}" if len(key) > 4 else "****"
    return config.model_copy(update={"provider_api_key": masked})


def resolve_provider_config(config: ProviderConfig) -> ProviderConfig:
    """Undo masking on write: a key containing ``*`` is the masked value
    round-tripped by the client and means "keep the stored key". Real keys
    never contain ``*``; an empty string still clears the key."""
    if "*" in config.provider_api_key:
        stored = get_provider_config().provider_api_key
        return config.model_copy(update={"provider_api_key": stored})
    return config


def _clamp_rounds(value: object) -> int:
    try:
        rounds = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 3
    return max(1, min(rounds, 10))


def get_provider_config() -> ProviderConfig:
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM app_config").fetchall()

    values = {row["key"]: row["value"] for row in rows}
    ocr_mode = values.get("ocr_mode") or "auto"
    if ocr_mode not in ("auto", "always"):
        ocr_mode = "auto"
    retrieval_mode = values.get("retrieval_mode") or "hybrid"
    if retrieval_mode not in ("vector", "hybrid"):
        retrieval_mode = "hybrid"
    agent_tool_protocol = values.get("agent_tool_protocol") or "prompt"
    if agent_tool_protocol not in ("prompt", "native"):
        agent_tool_protocol = "prompt"
    return ProviderConfig(
        provider_type=values.get("provider_type", "ollama"),
        provider_base_url=values.get("provider_base_url", "http://localhost:11434/v1"),
        provider_api_key=values.get("provider_api_key", ""),
        embedding_model=values.get("embedding_model") or "bge-m3",
        ocr_enabled=(values.get("ocr_enabled") or "0") == "1",
        ocr_base_url=values.get("ocr_base_url") or "http://localhost:8118",
        ocr_mode=ocr_mode,
        retrieval_mode=retrieval_mode,
        rerank_enabled=(values.get("rerank_enabled") or "0") == "1",
        rerank_model=values.get("rerank_model") or "BAAI/bge-reranker-base",
        query_rewrite_enabled=(values.get("query_rewrite_enabled") or "1") == "1",
        agentic_retrieval_enabled=(values.get("agentic_retrieval_enabled") or "0") == "1",
        web_search_enabled=(values.get("web_search_enabled") or "0") == "1",
        agent_tool_protocol=agent_tool_protocol,
        agent_max_rounds=_clamp_rounds(values.get("agent_max_rounds", 3)),
    )


def update_provider_config(config: ProviderConfig) -> ProviderConfig:
    now = int(time.time() * 1000)
    ocr_mode = config.ocr_mode if config.ocr_mode in ("auto", "always") else "auto"
    retrieval_mode = config.retrieval_mode if config.retrieval_mode in ("vector", "hybrid") else "hybrid"
    agent_tool_protocol = config.agent_tool_protocol if config.agent_tool_protocol in ("prompt", "native") else "prompt"
    agent_max_rounds = _clamp_rounds(config.agent_max_rounds)
    stored = {
        "provider_type": config.provider_type,
        "provider_base_url": config.provider_base_url.strip(),
        "provider_api_key": config.provider_api_key.strip(),
        "embedding_model": (config.embedding_model or "bge-m3").strip(),
        "ocr_enabled": "1" if config.ocr_enabled else "0",
        "ocr_base_url": (config.ocr_base_url or "http://localhost:8118").strip(),
        "ocr_mode": ocr_mode,
        "retrieval_mode": retrieval_mode,
        "rerank_enabled": "1" if config.rerank_enabled else "0",
        "rerank_model": (config.rerank_model or "BAAI/bge-reranker-base").strip(),
        "query_rewrite_enabled": "1" if config.query_rewrite_enabled else "0",
        "agentic_retrieval_enabled": "1" if config.agentic_retrieval_enabled else "0",
        "web_search_enabled": "1" if config.web_search_enabled else "0",
        "agent_tool_protocol": agent_tool_protocol,
        "agent_max_rounds": str(agent_max_rounds),
    }

    with get_db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO app_config (key, value, updated_at) VALUES (?, ?, ?)",
            [(key, value, now) for key, value in stored.items()],
        )

    return ProviderConfig(
        provider_type=config.provider_type,
        provider_base_url=stored["provider_base_url"],
        provider_api_key=stored["provider_api_key"],
        embedding_model=stored["embedding_model"],
        ocr_enabled=config.ocr_enabled,
        ocr_base_url=stored["ocr_base_url"],
        ocr_mode=ocr_mode,
        retrieval_mode=retrieval_mode,
        rerank_enabled=config.rerank_enabled,
        rerank_model=stored["rerank_model"],
        query_rewrite_enabled=config.query_rewrite_enabled,
        agentic_retrieval_enabled=config.agentic_retrieval_enabled,
        web_search_enabled=config.web_search_enabled,
        agent_tool_protocol=agent_tool_protocol,
        agent_max_rounds=agent_max_rounds,
    )
