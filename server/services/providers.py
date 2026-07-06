from __future__ import annotations

import json
import os
import subprocess
from collections.abc import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from server.schemas.config import ProviderConfig, ProviderVerifyResult


TIMEOUT = httpx.Timeout(60.0, connect=10.0)
# Non-stream chat (agent decisions, tool summaries) can take minutes on a cold
# local model: Ollama first loads weights, then generates the full answer in
# one shot. 60s read timeouts were cutting these off mid-load.
CHAT_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


def _describe_error(exc: Exception) -> str:
    """httpx timeouts often stringify to ''; keep the exception type visible."""
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def _is_ollama_vision_request(messages: list[dict]) -> bool:
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if part.get("type") == "image_url":
                return True
    return False


def _extract_base64(data_url: str) -> str:
    if "," in data_url:
        return data_url.split(",", 1)[1]
    return data_url


def _normalize_urls(config: ProviderConfig) -> tuple[str, str]:
    base_url = config.provider_base_url.rstrip("/")
    if config.provider_type == "ollama":
        if base_url.endswith("/v1"):
            return base_url, base_url[:-3]
        return f"{base_url}/v1", base_url
    return base_url, base_url


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", "r", encoding="utf-8") as handle:
            version = handle.read().lower()
            return "microsoft" in version or "wsl" in version
    except OSError:
        return False


def _get_wsl_host_gateway() -> str | None:
    try:
        output = subprocess.check_output(
            ["sh", "-lc", "ip route | awk '/default/ {print $3; exit}'"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None
    return output or None


def _replace_host(base_url: str, host: str) -> str:
    parts = urlsplit(base_url)
    port = parts.port
    hostname = host if port is None else f"{host}:{port}"
    return urlunsplit((parts.scheme, hostname, parts.path, parts.query, parts.fragment))


def _candidate_configs(config: ProviderConfig) -> list[ProviderConfig]:
    candidates = [config]
    parts = urlsplit(config.provider_base_url)
    if not _is_wsl():
        return candidates

    if parts.hostname not in {"localhost", "127.0.0.1"}:
        return candidates

    gateway = _get_wsl_host_gateway()
    if not gateway:
        return candidates

    fallback_url = _replace_host(config.provider_base_url, gateway)
    if fallback_url == config.provider_base_url:
        return candidates

    candidates.append(
        config.model_copy(update={"provider_base_url": fallback_url})
    )
    return candidates


def _build_headers(config: ProviderConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.provider_api_key:
        headers["Authorization"] = f"Bearer {config.provider_api_key}"
    return headers


def _with_system_prompt(messages: list[dict], system_prompt: str | None) -> list[dict]:
    if not system_prompt:
        return messages
    return [{"role": "system", "content": system_prompt}, *messages]


def _format_sse_chunk(
    delta: str = "",
    finish_reason: str | None = None,
    usage: dict | None = None,
) -> bytes:
    payload: dict = {
        "choices": [
            {
                "delta": {"content": delta} if delta else {},
                "finish_reason": finish_reason,
            }
        ]
    }
    if usage:
        payload["usage"] = usage
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _ollama_usage(parsed: dict) -> dict | None:
    """Map Ollama's eval counters onto the OpenAI usage shape."""
    prompt_tokens = parsed.get("prompt_eval_count")
    completion_tokens = parsed.get("eval_count")
    if prompt_tokens is None and completion_tokens is None:
        return None
    prompt_tokens = int(prompt_tokens or 0)
    completion_tokens = int(completion_tokens or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _map_model_list(config: ProviderConfig, payload: dict) -> list[dict]:
    if config.provider_type == "ollama" and isinstance(payload.get("models"), list):
        return [
            {
                "id": model.get("model", ""),
                "name": model.get("name") or model.get("model", ""),
                "size": model.get("size"),
                "modified_at": model.get("modified_at"),
            }
            for model in payload["models"]
        ]

    data = payload.get("data") or payload.get("models") or []
    return [
        {
            "id": model.get("id") or model.get("name", ""),
            "name": model.get("id") or model.get("name", ""),
            "size": model.get("size"),
            "modified_at": model.get("modified_at"),
        }
        for model in data
    ]


def _build_openai_body(
    config: ProviderConfig,
    payload: dict,
) -> dict:
    messages = _with_system_prompt(payload["messages"], payload.get("system_prompt"))
    body = {
        "model": payload["model"],
        "messages": messages,
        "stream": payload.get("stream", True),
        "temperature": payload.get("temperature", 0.7),
        "max_tokens": payload.get("max_tokens", 4096),
    }
    if body["stream"]:
        # Ask OpenAI-compatible upstreams (OpenAI/Ollama/vLLM) to emit a final
        # usage frame; unknown-field-tolerant servers simply ignore it.
        body["stream_options"] = {"include_usage": True}
    if payload.get("tools"):
        body["tools"] = payload["tools"]
    if config.provider_type == "ollama":
        body["chat_template_kwargs"] = {"enable_thinking": False}
    return body


def _build_ollama_body(payload: dict) -> dict:
    messages = _with_system_prompt(payload["messages"], payload.get("system_prompt"))
    ollama_messages: list[dict] = []

    for message in messages:
        content = message.get("content", "")
        image_values: list[str] = []
        text_chunks: list[str] = []

        if isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    text_chunks.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url:
                        image_values.append(_extract_base64(url))
        else:
            text_chunks.append(str(content))

        normalized = {
            "role": message.get("role", "user"),
            "content": "".join(text_chunks),
        }
        if image_values:
            normalized["images"] = image_values
        # Native function calling: keep assistant tool_calls in the replayed
        # history so the model sees which call each tool result answers.
        if message.get("tool_calls"):
            normalized["tool_calls"] = message["tool_calls"]
        ollama_messages.append(normalized)

    body = {
        "model": payload["model"],
        "messages": ollama_messages,
        "stream": payload.get("stream", True),
        "think": False,
        "options": {
            "temperature": payload.get("temperature", 0.7),
            "num_predict": payload.get("max_tokens", 4096),
        },
    }
    if payload.get("tools"):
        body["tools"] = payload["tools"]
    return body


async def _fetch_models_with_details(config: ProviderConfig) -> tuple[list[dict], ProviderConfig, str]:
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for candidate in _candidate_configs(config):
            openai_base_url, ollama_native_url = _normalize_urls(candidate)
            headers = _build_headers(candidate)
            endpoint_url = f"{ollama_native_url}/api/tags" if candidate.provider_type == "ollama" else f"{openai_base_url}/models"
            try:
                if candidate.provider_type == "ollama":
                    response = await client.get(endpoint_url, headers=headers)
                else:
                    response = await client.get(endpoint_url, headers=headers)
                response.raise_for_status()
                return _map_model_list(candidate, response.json()), candidate, endpoint_url
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise HTTPException(status_code=502, detail=f"Model request failed: {exc}") from exc

    raise HTTPException(status_code=502, detail=f"Model request failed: {last_error}") from last_error


async def fetch_models(config: ProviderConfig) -> list[dict]:
    models, _, _ = await _fetch_models_with_details(config)
    return models


async def verify_provider_config(config: ProviderConfig) -> ProviderVerifyResult:
    try:
        models, resolved_config, endpoint_url = await _fetch_models_with_details(config)
        return ProviderVerifyResult(
            ok=True,
            provider_type=config.provider_type,
            configured_base_url=config.provider_base_url,
            resolved_base_url=resolved_config.provider_base_url,
            endpoint_url=endpoint_url,
            models_count=len(models),
            models=models,
        )
    except HTTPException as exc:
        return ProviderVerifyResult(
            ok=False,
            provider_type=config.provider_type,
            configured_base_url=config.provider_base_url,
            error=str(exc.detail),
        )
    except Exception as exc:
        return ProviderVerifyResult(
            ok=False,
            provider_type=config.provider_type,
            configured_base_url=config.provider_base_url,
            error=str(exc),
        )


async def _stream_openai_response(response: httpx.Response) -> AsyncIterator[bytes]:
    async for chunk in response.aiter_bytes():
        if chunk:
            yield chunk


async def _stream_ollama_response(response: httpx.Response) -> AsyncIterator[bytes]:
    buffer = ""
    async for chunk in response.aiter_text():
        buffer += chunk
        lines = buffer.split("\n")
        buffer = lines.pop() or ""

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            if parsed.get("error"):
                raise HTTPException(status_code=502, detail=str(parsed["error"]))

            content = parsed.get("message", {}).get("content", "")
            if content:
                yield _format_sse_chunk(delta=content)

            if parsed.get("done") is True:
                yield _format_sse_chunk(finish_reason="stop", usage=_ollama_usage(parsed))
                yield b"data: [DONE]\n\n"
                return

    if buffer.strip():
        try:
            parsed = json.loads(buffer.strip())
        except json.JSONDecodeError:
            parsed = {}
        content = parsed.get("message", {}).get("content", "")
        if content:
            yield _format_sse_chunk(delta=content)

    yield _format_sse_chunk(finish_reason="stop")
    yield b"data: [DONE]\n\n"


async def create_chat_completion(config: ProviderConfig, payload: dict):
    if payload.get("stream", True):
        async def iterator() -> AsyncIterator[bytes]:
            last_error: Exception | None = None
            for candidate in _candidate_configs(config):
                openai_base_url, ollama_native_url = _normalize_urls(candidate)
                headers = _build_headers(candidate)
                use_ollama_native = candidate.provider_type == "ollama"
                url = f"{ollama_native_url}/api/chat" if use_ollama_native else f"{openai_base_url}/chat/completions"
                body = _build_ollama_body(payload) if use_ollama_native else _build_openai_body(candidate, payload)
                try:
                    async with httpx.AsyncClient(timeout=None) as client:
                        async with client.stream("POST", url, headers=headers, json=body) as response:
                            response.raise_for_status()
                            stream = _stream_ollama_response(response) if use_ollama_native else _stream_openai_response(response)
                            async for chunk in stream:
                                yield chunk
                            return
                except httpx.RequestError as exc:
                    last_error = exc
                    continue
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    break

            if last_error is not None:
                yield _format_sse_chunk(delta=f"Error: {_describe_error(last_error)}")
                yield _format_sse_chunk(finish_reason="stop")
                yield b"data: [DONE]\n\n"

        return StreamingResponse(iterator(), media_type="text/event-stream")

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=CHAT_TIMEOUT) as client:
        for candidate in _candidate_configs(config):
            openai_base_url, ollama_native_url = _normalize_urls(candidate)
            headers = _build_headers(candidate)
            use_ollama_native = candidate.provider_type == "ollama"
            url = f"{ollama_native_url}/api/chat" if use_ollama_native else f"{openai_base_url}/chat/completions"
            body = _build_ollama_body(payload) if use_ollama_native else _build_openai_body(candidate, payload)
            try:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=502, detail=f"Chat request failed: {_describe_error(exc)}"
                ) from exc

            if use_ollama_native:
                result = response.json()
                raw_message = result.get("message", {})
                message: dict = {
                    "role": "assistant",
                    "content": raw_message.get("content", ""),
                }
                if raw_message.get("tool_calls"):
                    message["tool_calls"] = raw_message["tool_calls"]
                normalized: dict = {
                    "id": result.get("id", "chatcmpl-ollama"),
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": message,
                            "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                        }
                    ],
                }
                usage = _ollama_usage(result)
                if usage:
                    normalized["usage"] = usage
                return normalized

            return response.json()

    raise HTTPException(
        status_code=502,
        detail=f"Chat request failed: {_describe_error(last_error)}" if last_error else "Chat request failed",
    ) from last_error


async def create_chat_completion_full(config: ProviderConfig, payload: dict) -> dict:
    """Non-stream completion returning the whole normalized response
    (choices + usage). Callers that need token accounting use this."""
    result = await create_chat_completion(config, {**payload, "stream": False})
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Non-stream chat request returned an unexpected response")
    return result


async def create_chat_completion_text(config: ProviderConfig, payload: dict) -> str:
    result = await create_chat_completion_full(config, payload)
    return str(result.get("choices", [{}])[0].get("message", {}).get("content", ""))


async def create_chat_completion_message(config: ProviderConfig, payload: dict) -> dict:
    """Non-stream completion returning the full assistant message (content +
    tool_calls). Used by the agent's native function-calling protocol."""
    result = await create_chat_completion_full(config, payload)
    message = result.get("choices", [{}])[0].get("message", {})
    return message if isinstance(message, dict) else {"role": "assistant", "content": str(message)}
