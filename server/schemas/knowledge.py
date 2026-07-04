from __future__ import annotations

from pydantic import BaseModel, Field

from server.schemas.file import FileRecord


class Knowledge(BaseModel):
    id: str
    name: str
    description: str = ""
    file_count: int = 0
    chunk_count: int = 0
    created_at: int
    updated_at: int


class KnowledgeDetail(Knowledge):
    files: list[FileRecord] = Field(default_factory=list)


class KnowledgeCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class KnowledgeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class KnowledgeListResponse(BaseModel):
    knowledge: list[Knowledge]


class BindFileRequest(BaseModel):
    file_id: str = Field(min_length=1)


class RetrievalQuery(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = 4
    # Optional overrides for A/B debugging; None falls back to app config.
    mode: str | None = None
    rerank: bool | None = None


class RetrievalChunk(BaseModel):
    chunk_id: str
    file_id: str
    filename: str
    chunk_index: int
    content: str
    score: float


class RetrievalResult(BaseModel):
    chunks: list[RetrievalChunk]


class IndexResult(BaseModel):
    knowledge_id: str
    files: int
    chunks: int
    embedding_model: str
