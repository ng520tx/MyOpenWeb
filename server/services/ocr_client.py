from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from server.schemas.config import ProviderConfig
from server.services.providers import _get_wsl_host_gateway, _is_wsl, _replace_host


# PDF/image parsing on CPU can be slow, so allow a long read window.
OCR_TIMEOUT = httpx.Timeout(600.0, connect=10.0)

# Image suffixes the OCR service can read directly.
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}


class OcrError(RuntimeError):
    """Raised when the OCR service is unreachable or returns an error.

    Callers are expected to catch this and fall back to plain extraction
    instead of failing the upload.
    """


def is_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in IMAGE_SUFFIXES


def _candidate_urls(base_url: str) -> list[str]:
    """Return OCR service URLs to try, adding the WSL host gateway fallback.

    Mirrors the provider host fallback so a backend running inside WSL can
    still reach an OCR service listening on the Windows host's localhost.
    """
    base = (base_url or "").rstrip("/")
    candidates = [base]
    parts = urlsplit(base)
    if not _is_wsl() or parts.hostname not in {"localhost", "127.0.0.1"}:
        return candidates
    gateway = _get_wsl_host_gateway()
    if not gateway:
        return candidates
    fallback = _replace_host(base, gateway)
    if fallback and fallback != base:
        candidates.append(fallback)
    return candidates


def _collect_markdown(data: dict) -> str:
    """Pull layout-aware Markdown out of a PP-StructureV3 serving response."""
    result = data.get("result") if isinstance(data, dict) else None
    items = (result or {}).get("layoutParsingResults") or []
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        markdown = item.get("markdown")
        text = ""
        if isinstance(markdown, dict):
            text = markdown.get("text") or ""
        elif isinstance(markdown, str):
            text = markdown
        if not text:
            text = item.get("text") or ""
        if text and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


async def parse_document(config: ProviderConfig, raw: bytes, filename: str) -> str:
    """Send a PDF/image to the PP-StructureV3 serving API and return Markdown.

    Raises OcrError on any connection/protocol problem so the caller can fall
    back to the plain-text extractor.
    """
    base_url = (config.ocr_base_url or "").strip()
    if not base_url:
        raise OcrError("未配置 OCR 服务地址")

    suffix = Path(filename).suffix.lower()
    file_type = 1 if suffix == ".pdf" else 0
    payload = {
        "file": base64.b64encode(raw).decode("ascii"),
        "fileType": file_type,
        "useChartRecognition": False,
        "useDocOrientationClassify": False,
    }

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=OCR_TIMEOUT) as client:
        for base in _candidate_urls(base_url):
            url = f"{base}/layout-parsing"
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            except httpx.RequestError as exc:
                last_error = exc
                continue
            except httpx.HTTPStatusError as exc:
                raise OcrError(f"OCR 服务返回错误：{exc}") from exc

            try:
                markdown = _collect_markdown(response.json())
            except ValueError as exc:  # invalid JSON
                raise OcrError(f"OCR 响应解析失败：{exc}") from exc
            return markdown

    raise OcrError(f"无法连接 OCR 服务（{base_url}）：{last_error}")
