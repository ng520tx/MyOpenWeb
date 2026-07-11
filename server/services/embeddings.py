from __future__ import annotations

import httpx
from fastapi import HTTPException

from server.schemas.config import ProviderConfig
from server.services.providers import _build_headers, _candidate_configs, _normalize_urls

TIMEOUT = httpx.Timeout(120.0, connect=10.0)


async def embed_texts(config: ProviderConfig, model: str, texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input text.

    Works against Ollama native ``/api/embed`` (batch) and OpenAI-compatible
    ``/embeddings``. Reuses the WSL host fallback from the provider service so
    a backend running in WSL can still reach Ollama on the Windows host.
    """
    if not texts:
        return []

    model = (model or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="未配置 embedding 模型，请在设置中填写")

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for candidate in _candidate_configs(config):
            openai_base_url, ollama_native_url = _normalize_urls(candidate)
            headers = _build_headers(candidate)
            try:
                if candidate.provider_type == "ollama":
                    response = await client.post(
                        f"{ollama_native_url}/api/embed",
                        headers=headers,
                        json={"model": model, "input": texts},
                    )
                    response.raise_for_status()
                    embeddings = response.json().get("embeddings")
                    if not embeddings:
                        raise HTTPException(
                            status_code=502,
                            detail=(
                                f"Ollama 未返回向量，请确认已执行 'ollama pull {model}'"
                            ),
                        )
                    return embeddings

                response = await client.post(
                    f"{openai_base_url}/embeddings",
                    headers=headers,
                    json={"model": model, "input": texts},
                )
                response.raise_for_status()
                data = response.json().get("data", [])
                ordered = sorted(data, key=lambda item: item.get("index", 0))
                return [item["embedding"] for item in ordered]
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Embedding 请求失败：{exc}. 请确认 embedding 模型 '{model}' 已安装",
                ) from exc

    raise HTTPException(status_code=502, detail=f"Embedding 请求失败：{last_error}") from last_error


async def embed_query(config: ProviderConfig, model: str, text: str) -> list[float]:
    vectors = await embed_texts(config, model, [text])
    return vectors[0] if vectors else []
