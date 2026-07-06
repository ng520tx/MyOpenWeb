from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ProviderType = Literal["ollama", "openai"]
OcrMode = Literal["auto", "always"]
RetrievalMode = Literal["vector", "hybrid"]
AgentToolProtocol = Literal["prompt", "native"]


class ProviderConfig(BaseModel):
    provider_type: ProviderType = "ollama"
    provider_base_url: str = Field(default="http://localhost:11434/v1", min_length=1)
    provider_api_key: str = ""
    embedding_model: str = "bge-m3"
    # OCR document parsing (PP-StructureV3) runs as a separate local service.
    ocr_enabled: bool = False
    ocr_base_url: str = "http://localhost:8118"
    ocr_mode: OcrMode = "auto"
    # Retrieval strategy: pure vector cosine, or hybrid (BM25 via SQLite FTS5
    # fused with vector ranks through Reciprocal Rank Fusion).
    retrieval_mode: RetrievalMode = "hybrid"
    # Optional cross-encoder rerank stage (bge-reranker). Heavy deps are lazily
    # imported; when unavailable retrieval silently falls back to fused order.
    rerank_enabled: bool = False
    rerank_model: str = "BAAI/bge-reranker-base"
    # Rewrite the latest user turn into a self-contained retrieval query using
    # recent chat history (resolves pronouns like "它的端口"). Falls back to the
    # raw query on any failure; single-turn chats skip the extra LLM call.
    query_rewrite_enabled: bool = True
    # Agentic retrieval self-correction: after retrieving, a temperature=0
    # grader call judges whether the chunks can answer the question; if not,
    # one bounded follow-up retrieval targets the missing information. Grader
    # failures fall back to first-pass results.
    agentic_retrieval_enabled: bool = False
    # Expose the web_search tool to the agent (ddgs / DuckDuckGo, no API key).
    # Search failures degrade to a structured error the model can relay.
    web_search_enabled: bool = False
    # Agent tool-calling protocol: "prompt" instructs the model to emit a JSON
    # decision (works with any model), "native" uses the provider's function
    # calling API (requires model-side tools support, e.g. qwen2.5).
    agent_tool_protocol: AgentToolProtocol = "prompt"


class ProviderVerifyResult(BaseModel):
    ok: bool
    provider_type: ProviderType
    configured_base_url: str
    resolved_base_url: str | None = None
    endpoint_url: str | None = None
    models_count: int = 0
    models: list[dict] = Field(default_factory=list)
    error: str | None = None
