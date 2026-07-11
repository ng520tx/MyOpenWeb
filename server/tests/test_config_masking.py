"""Provider API key must never leave the backend in plaintext.

GET responses carry a ``***xxxx`` fingerprint; a masked key round-tripped
back through PUT/verify means "keep the stored key" while an empty string
still clears it.
"""
from __future__ import annotations

from server.repositories.configs import (
    get_provider_config,
    mask_provider_config,
    resolve_provider_config,
    update_provider_config,
)


def _set_key(key: str) -> None:
    config = get_provider_config()
    update_provider_config(config.model_copy(update={"provider_api_key": key}))


def test_mask_keeps_only_a_fingerprint():
    config = get_provider_config().model_copy(update={"provider_api_key": "sk-secret-1234"})
    assert mask_provider_config(config).provider_api_key == "***1234"


def test_mask_short_and_empty_keys():
    config = get_provider_config()
    assert mask_provider_config(config.model_copy(update={"provider_api_key": ""})).provider_api_key == ""
    assert mask_provider_config(config.model_copy(update={"provider_api_key": "abc"})).provider_api_key == "****"


def test_masked_roundtrip_preserves_stored_key():
    _set_key("sk-real-key-abcd")
    try:
        masked = mask_provider_config(get_provider_config())
        resolved = resolve_provider_config(masked)
        assert resolved.provider_api_key == "sk-real-key-abcd"
    finally:
        _set_key("")


def test_new_key_and_empty_key_pass_through():
    _set_key("sk-old-key-1234")
    try:
        config = get_provider_config().model_copy(update={"provider_api_key": "sk-new-key-5678"})
        assert resolve_provider_config(config).provider_api_key == "sk-new-key-5678"

        cleared = get_provider_config().model_copy(update={"provider_api_key": ""})
        assert resolve_provider_config(cleared).provider_api_key == ""
    finally:
        _set_key("")
