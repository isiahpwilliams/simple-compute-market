"""Inference listing resource schema.

The listing's ``listing_resource`` is a model card: one served model at one
seller. ``model_id`` is seller-asserted; ``identity.derive_model_id`` is the
convention sellers of the same weights should share. ``resource_id`` names the
quota resource the listing derives from — seller-internal bookkeeping the
reconciler and quota guard key on; buyers ignore it.
"""

from __future__ import annotations

import json
from typing import Any, Literal, get_args

from market_identity import Identity
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

INFERENCE_KIND = "inference.v1"
INFERENCE_OFFERING_MODE = "inference"
OPENAI_V1_API_STYLE = "openai.v1"

Quantization = Literal["none", "fp16", "bf16", "fp8", "int8", "int4", "awq", "gptq"]
Provenance = Literal["self-hosted", "resold"]

QUANTIZATIONS: tuple[str, ...] = get_args(Quantization)
PROVENANCES: tuple[str, ...] = get_args(Provenance)

_MODEL_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$"
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


class InferenceRateCard(BaseModel):
    """Prices in base units of the listing's settlement asset."""

    model_config = ConfigDict(extra="forbid")

    prompt_credits_per_million: StrictInt = Field(ge=0)
    completion_credits_per_million: StrictInt = Field(ge=0)
    request_credits: StrictInt = Field(default=0, ge=0)
    cached_prompt_credits_per_million: StrictInt | None = Field(default=None, ge=0)
    image_credits_per_unit: StrictInt | None = Field(default=None, ge=0)


class InferenceArchitecture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modality: str = Field(min_length=1)
    tokenizer: str | None = None
    instruct_type: str | None = None


class InferenceEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(min_length=1)
    openapi_url: str | None = None
    api_style: Literal["openai.v1"] = OPENAI_V1_API_STYLE


class AttestationEnvelope(BaseModel):
    """Opaque, unverified in this version; a proof format is a later ``kind``."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    schema_version: StrictInt = Field(ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class InferenceModelCard(BaseModel):
    """``listing_resource`` payload for an inference listing."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["inference.v1"] = INFERENCE_KIND
    model_id: str = Field(pattern=_MODEL_ID_PATTERN)
    artifact_ref: str = Field(min_length=1)
    artifact_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    display_name: str | None = None
    model_owner: Identity | None = None
    provenance: Provenance
    served_model_name: str = Field(min_length=1)
    model_family: str | None = None
    context_length: int = Field(gt=0)
    max_completion_tokens: int | None = Field(default=None, gt=0)
    quantization: Quantization
    architecture: InferenceArchitecture
    supported_parameters: list[str]
    endpoint: InferenceEndpoint
    rate_card: InferenceRateCard
    attestation: AttestationEnvelope | None = None
    capacity_site_id: str = Field(min_length=1)
    resource_id: str | None = Field(default=None, min_length=1)
    offering_mode: Literal["inference"] = INFERENCE_OFFERING_MODE

    @field_validator("served_model_name", "artifact_ref", "capacity_site_id", "resource_id")
    @classmethod
    def _non_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("supported_parameters")
    @classmethod
    def _non_blank_parameters(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("supported_parameters entries must be non-empty")
        return value


def coerce_resource_dict(value: Any) -> dict[str, Any]:
    """Best-effort dict view of a listing_resource (SQLite stores JSON text)."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def resource_is_inference(resource: Any) -> bool:
    """True when the resource is an inference offering."""
    if isinstance(resource, InferenceModelCard):
        return True
    coerced = coerce_resource_dict(resource)
    return coerced.get("kind") == INFERENCE_KIND
