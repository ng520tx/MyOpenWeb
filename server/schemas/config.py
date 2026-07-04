from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ProviderType = Literal["ollama", "openai"]
OcrMode = Literal["auto", "always"]


class ProviderConfig(BaseModel):
    provider_type: ProviderType = "ollama"
    provider_base_url: str = Field(default="http://localhost:11434/v1", min_length=1)
    provider_api_key: str = ""
    embedding_model: str = "bge-m3"
    # OCR document parsing (PP-StructureV3) runs as a separate local service.
    ocr_enabled: bool = False
    ocr_base_url: str = "http://localhost:8118"
    ocr_mode: OcrMode = "auto"


class ProviderVerifyResult(BaseModel):
    ok: bool
    provider_type: ProviderType
    configured_base_url: str
    resolved_base_url: str | None = None
    endpoint_url: str | None = None
    models_count: int = 0
    models: list[dict] = Field(default_factory=list)
    error: str | None = None
