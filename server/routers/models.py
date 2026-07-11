from __future__ import annotations

from fastapi import APIRouter

from server.repositories.configs import get_provider_config
from server.services.providers import fetch_models

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
async def get_models() -> dict[str, list[dict]]:
    config = get_provider_config()
    models = await fetch_models(config)
    return {"data": models}
