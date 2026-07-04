from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FileRecord(BaseModel):
    id: str
    filename: str
    mime_type: str | None = None
    size: int = 0
    hash: str | None = None
    text_preview: str = ""
    text_length: int = 0
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: int
    updated_at: int


class FileDetail(FileRecord):
    text_content: str = ""


class FilesResponse(BaseModel):
    files: list[FileRecord]
