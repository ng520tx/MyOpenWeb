from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MemoryCategory = Literal["preference", "profile", "project", "fact"]


class Memory(BaseModel):
    id: str
    content: str
    category: MemoryCategory = "fact"
    enabled: bool = True
    created_at: int
    updated_at: int


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1)
    category: MemoryCategory = "fact"
    enabled: bool = True


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    category: MemoryCategory | None = None
    enabled: bool | None = None


class MemoriesResponse(BaseModel):
    memories: list[Memory]
