from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FileAttachment(BaseModel):
    name: str
    size: int
    type: str
    content: str = ""
    isImage: bool | None = None
    dataUrl: str | None = None


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: int
    done: bool
    error: str | None = None
    model: str | None = None
    files: list[FileAttachment] | None = None


class Conversation(BaseModel):
    id: str
    title: str
    messages: list[ChatMessage] = Field(default_factory=list)
    createdAt: int
    updatedAt: int


class ConversationsResponse(BaseModel):
    conversations: list[Conversation]


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    stream: bool = True
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: str | None = None
    knowledge_id: str | None = None
    rag_top_k: int = 4
    metadata: dict[str, Any] = Field(default_factory=dict)
