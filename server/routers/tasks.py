from __future__ import annotations

from fastapi import APIRouter

from server.repositories.configs import get_provider_config
from server.schemas.tasks import (
    FollowUpsRequest,
    FollowUpsResult,
    TitleRequest,
    TitleResult,
)
from server.services.llm_tasks import generate_follow_ups, generate_title

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/title", response_model=TitleResult)
async def create_title(payload: TitleRequest) -> TitleResult:
    config = get_provider_config()
    title = await generate_title(config, payload.model, payload.user_text, payload.assistant_text)
    return TitleResult(title=title)


@router.post("/follow_ups", response_model=FollowUpsResult)
async def create_follow_ups(payload: FollowUpsRequest) -> FollowUpsResult:
    config = get_provider_config()
    follow_ups = await generate_follow_ups(config, payload.model, payload.messages)
    return FollowUpsResult(follow_ups=follow_ups)
