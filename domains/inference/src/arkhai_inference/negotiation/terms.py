"""Inference provision-term construction.

``ProvisionTerms{kind: "inference.v1", version: 1, payload: ...}`` is fixed at
round 0. ``quantity`` is base units of the settlement asset to place on the
key; ``key`` is the buyer's key disposition: ``{"mode": "new"}`` or
``{"mode": "existing", "key_id": "ak_…"}``. The shape is the API-credits
purchase shape by design; whether it becomes kit-owned is decided with two
consumers in view.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

INFERENCE_PROVISION_KIND = "inference.v1"
INFERENCE_PROVISION_VERSION = 1


class InferenceKeyIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["new", "existing"] = "new"
    key_id: str | None = None

    @model_validator(mode="after")
    def _validate_existing_key(self) -> "InferenceKeyIntent":
        if self.mode == "existing" and not self.key_id:
            raise ValueError("key.key_id is required when key.mode is existing")
        return self


class InferenceProvisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: int = Field(ge=1)
    key: InferenceKeyIntent = Field(default_factory=InferenceKeyIntent)


class InferenceProvisionTerms(BaseModel):
    """Inference provision envelope with domain-owned payload validation."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["inference.v1"] = INFERENCE_PROVISION_KIND
    version: Literal[1] = INFERENCE_PROVISION_VERSION
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def _validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return InferenceProvisionPayload.model_validate(value).model_dump(
            exclude_none=True,
        )

    @property
    def quantity(self) -> int | None:
        raw = self.payload.get("quantity")
        return int(raw) if raw is not None else None

    @property
    def key_mode(self) -> str:
        key = self.payload.get("key")
        mode = key.get("mode") if isinstance(key, dict) else None
        return mode if isinstance(mode, str) else "new"

    @property
    def key_id(self) -> str | None:
        key = self.payload.get("key")
        raw = key.get("key_id") if isinstance(key, dict) else None
        return str(raw) if raw else None


def make_inference_provision_terms(
    *,
    quantity: int,
    key_mode: str = "new",
    key_id: str | None = None,
) -> InferenceProvisionTerms:
    key: dict[str, Any] = {"mode": key_mode}
    if key_id is not None:
        key["key_id"] = key_id
    return InferenceProvisionTerms(
        payload={"quantity": int(quantity), "key": key},
    )


def provision_payload(terms: Any) -> dict[str, Any]:
    if isinstance(terms, dict):
        raw = terms.get("payload")
    else:
        raw = getattr(terms, "payload", None)
    return raw if isinstance(raw, dict) else {}


def provision_quantity(terms: Any) -> int | None:
    raw = provision_payload(terms).get("quantity")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def provision_key_mode(terms: Any) -> str:
    key = provision_payload(terms).get("key")
    mode = key.get("mode") if isinstance(key, dict) else None
    return mode if isinstance(mode, str) and mode else "new"


def provision_key_id(terms: Any) -> str | None:
    key = provision_payload(terms).get("key")
    raw = key.get("key_id") if isinstance(key, dict) else None
    return str(raw) if raw else None
