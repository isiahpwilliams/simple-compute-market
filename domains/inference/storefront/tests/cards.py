"""Model cards the storefront tests publish. Every address is a deterministic development value."""

from __future__ import annotations

from typing import Any

ASSET = "0x" + "01" * 20


def model_card(**fields: Any) -> dict[str, Any]:
    """An operator's card as a publish request carries it, before its quota binds it."""
    card: dict[str, Any] = {
        "model_id": "arkhai/stub-instruct",
        "artifact_ref": "dev://arkhai/stub-instruct",
        "provenance": "self-hosted",
        "served_model_name": "stub-instruct",
        "context_length": 8192,
        "quantization": "none",
        "architecture": {"modality": "text->text"},
        "supported_parameters": ["max_tokens", "stream"],
        "endpoint": {"base_url": "http://gateway.test/v1"},
        "rate_card": {
            "asset": ASSET,
            "prompt_credits_per_million": 0,
            "completion_credits_per_million": 0,
            "request_credits": 3,
        },
    }
    card.update(fields)
    return card


def bound_card(*, resource_id: str = "svc-quota", site_id: str = "tokens", **fields: Any) -> dict[str, Any]:
    """A card bound to its quota, as a published listing carries it."""
    return {
        **model_card(**fields),
        "kind": "inference.v1",
        "resource_id": resource_id,
        "capacity_site_id": site_id,
        "offering_mode": "inference",
    }
