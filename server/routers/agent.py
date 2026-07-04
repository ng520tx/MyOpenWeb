from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.repositories.agent_runs import get_agent_run
from server.repositories.configs import get_provider_config
from server.schemas.chat import ChatCompletionRequest
from server.services.agent_runner import create_agent_completion


router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/agent/completions")
async def agent_completions(payload: ChatCompletionRequest):
    config = get_provider_config()
    return await create_agent_completion(config, payload.model_dump())


@router.get("/agent/runs/{run_id}")
async def get_agent_run_by_id(run_id: str):
    run = get_agent_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run
