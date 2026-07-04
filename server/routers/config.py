from __future__ import annotations

from fastapi import APIRouter

from server.repositories.configs import get_provider_config, update_provider_config
from server.schemas.config import ProviderConfig, ProviderVerifyResult
from server.services.providers import verify_provider_config


router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/provider", response_model=ProviderConfig)
def get_provider() -> ProviderConfig:
    return get_provider_config()


@router.put("/provider", response_model=ProviderConfig)
def put_provider(config: ProviderConfig) -> ProviderConfig:
    return update_provider_config(config)


@router.post("/provider/verify", response_model=ProviderVerifyResult)
async def verify_provider(config: ProviderConfig) -> ProviderVerifyResult:
    return await verify_provider_config(config)
