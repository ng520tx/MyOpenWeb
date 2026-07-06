from __future__ import annotations

from pydantic import BaseModel, Field


class TitleRequest(BaseModel):
    model: str = Field(min_length=1)
    user_text: str = Field(min_length=1)
    assistant_text: str = ""


class TitleResult(BaseModel):
    title: str | None = None


class FollowUpsRequest(BaseModel):
    model: str = Field(min_length=1)
    messages: list[dict] = Field(default_factory=list)


class FollowUpsResult(BaseModel):
    follow_ups: list[str] = Field(default_factory=list)
