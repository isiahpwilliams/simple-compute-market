"""Inference implementation of the core market-domain contract."""

from __future__ import annotations

from typing import Any

from market_core import (
    MARKET_DOMAIN_CONTRACT_VERSION,
    DomainIdentity,
    ImmutableCodecCapability,
    MarketDomainContract,
)

from domains.inference.schema import (
    INFERENCE_SCHEMA_KIND,
    InferenceListing,
    InferenceMaterialization,
    InferenceMessage,
    InferenceReceipt,
    InferenceResult,
    InferenceTerms,
)


def _normalize_listing(value: Any) -> InferenceListing:
    return InferenceListing.model_validate(value)


def _normalize_message(value: Any) -> InferenceMessage:
    return InferenceMessage.model_validate(value)


def _normalize_terms(value: Any) -> InferenceTerms:
    return InferenceTerms.model_validate(value)


def _normalize_materialization(value: Any) -> InferenceMaterialization:
    return InferenceMaterialization.model_validate(value)


def _normalize_receipt(value: Any) -> InferenceReceipt:
    return InferenceReceipt.model_validate(value)


def _normalize_result(value: Any) -> InferenceResult:
    return InferenceResult.model_validate(value)


INFERENCE_MARKET_DOMAIN = MarketDomainContract(
    identity=DomainIdentity(INFERENCE_SCHEMA_KIND),
    contract_version=MARKET_DOMAIN_CONTRACT_VERSION,
    codecs=ImmutableCodecCapability(
        normalize_listing=_normalize_listing,
        normalize_message=_normalize_message,
        normalize_terms=_normalize_terms,
        normalize_materialization=_normalize_materialization,
        normalize_receipt=_normalize_receipt,
        normalize_result=_normalize_result,
    ),
)


def market_domain() -> MarketDomainContract:
    """Return the inference market-domain contract."""
    return INFERENCE_MARKET_DOMAIN
