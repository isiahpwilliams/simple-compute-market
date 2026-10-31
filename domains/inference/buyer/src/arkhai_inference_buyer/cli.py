"""Inference market-domain contribution for the core ``market`` buyer CLI."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import typer
from arkhai_api_buying.commands import command_group
from arkhai_api_buying.contributions import BuyingContributions, ListingRendering
from arkhai_api_buying.settlement_composition import BuyerSettlementComposition
from arkhai_inference.domain_runtime import market_domain
from arkhai_inference.listings import coerce_resource_dict
from arkhai_inference.negotiation import InferenceProvisionTerms, make_inference_provision_terms
from core_buyer.cli import build_app
from core_buyer.policy_surface import configured_buyer_policy
from market_core import (
    BUYER_IDENTITY_INJECTION_CONTRACT,
    DomainCapability,
    ImmutableBuyerCapability,
    MarketDomainContract,
    SettlementStageTable,
)

from arkhai_inference_buyer.verification import VerifyingAlkahestStage


def _text(value: Any) -> str:
    return "-" if value is None or value == "" else str(value)


def _summary(resource: Mapping[str, Any]) -> str:
    if not resource:
        return "-"
    model = _text(resource.get("model_id"))
    served = resource.get("served_model_name")
    return model if not served or served == model else f"{model} (as {served})"


def _request_charge(resource: Mapping[str, Any]) -> str:
    return _text((resource.get("rate_card") or {}).get("request_credits"))


def _details(resource: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    rate_card = resource.get("rate_card") or {}
    attestation = resource.get("attestation") or {}
    return (
        ("Model", _text(resource.get("model_id"))),
        ("Display name", _text(resource.get("display_name"))),
        ("Served as", _text(resource.get("served_model_name"))),
        ("Artifact", _text(resource.get("artifact_ref"))),
        ("Artifact digest", _text(resource.get("artifact_digest"))),
        ("Provenance", _text(resource.get("provenance"))),
        ("Quantization", _text(resource.get("quantization"))),
        ("Context length", _text(resource.get("context_length"))),
        ("Base URL", _text((resource.get("endpoint") or {}).get("base_url"))),
        ("Rate asset", _text(rate_card.get("asset"))),
        ("Request charge", _request_charge(resource)),
        ("Attestation", _text(attestation.get("kind"))),
    )


#: The registry's filter-spec.yaml declares the same schema id.
CONTRIBUTIONS = BuyingContributions(
    schema_id="inference",
    provision_terms=InferenceProvisionTerms,
    command="inference",
    command_help="Inference market: discover models, buy request credits, top up keys.",
    noun="inference",
    resource_query_example="model_id=meta-llama/llama-3.1-8b-instruct quantization in [fp16,bf16]",
    rendering=ListingRendering(
        resource=coerce_resource_dict,
        summary_header="Model",
        summary=_summary,
        columns=(
            ("Quantization", lambda resource: _text(resource.get("quantization"))),
            ("Context", lambda resource: _text(resource.get("context_length"))),
            ("Provenance", lambda resource: _text(resource.get("provenance"))),
            ("Per request", _request_charge),
        ),
        details=_details,
    ),
)

#: Alkahest is the only inference settlement mechanism.
SETTLEMENT = BuyerSettlementComposition(
    CONTRIBUTIONS,
    SettlementStageTable((stage.mechanism_id, stage) for stage in (VerifyingAlkahestStage(),)),
)

inference_app = command_group(SETTLEMENT)


def register(app: typer.Typer) -> None:
    """Register the inference schema's buyer commands on the core app."""
    app.add_typer(inference_app, name=CONTRIBUTIONS.command, help=CONTRIBUTIONS.command_help)


def _buyer_market_domain() -> MarketDomainContract:
    base = market_domain()
    return replace(
        base,
        declared_capabilities=(base.declared_capabilities | {DomainCapability.BUYER}),
        buyer=ImmutableBuyerCapability(
            identity_injection_contract=BUYER_IDENTITY_INJECTION_CONTRACT,
            register_commands=register,
            build_provision_terms=make_inference_provision_terms,
            select_policy=configured_buyer_policy,
            decode_result=base.codecs.result,
        ),
    )


#: Loaded by ``market.buyer_domains`` discovery.
domain = _buyer_market_domain()

#: Pre-assembled app for direct module execution.
app = build_app(domains=[domain])


if __name__ == "__main__":
    app()
