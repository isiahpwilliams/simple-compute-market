"""inference storefront FastAPI application.

Mirrors the VM storefront's shape: ``FastAPI(lifespan=lifespan)``
resolves singletons and starts the background tasks; controllers mount
after the module-level app exists; admin auth via Security() on
individual routers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial
from typing import Any

from core_storefront.app_composition import StorefrontAppConfig
from core_storefront.domain_registry import (
    StorefrontDomainRegistry,
)
from core_storefront.services.negotiation_service import NegotiationService
from core_storefront.stage_log import set_stage_event_db_path, stage_event
from market_core import MarketDomainContract
from market_settlement_runtime import SettlementJobCoordinator
from market_storefront_kit import (
    AlkahestChain,
    AlkahestClientPolicy,
    StorefrontComposition,
    StorefrontRouteHooks,
    StorefrontServiceHooks,
    build_alkahest_clients,
    build_composed_storefront_app,
)

import inference_storefront.container as _container
from inference_storefront.domain_runtime import (
    fulfill_inference_settlement,
    get_market_domain_contract,
    persist_inference_settlement_outcome,
    prepare_inference_settlement,
    reserve_inference_settlement,
)
from inference_storefront.listing_binding import inference_registration
from inference_storefront.middleware.response_auth import authenticate_response
from inference_storefront.negotiation_runtime import (
    build_inference_negotiation_runtime,
)
from inference_storefront.services.fulfillment_service import (
    build_inference_failure_policy,
)
from inference_storefront.services.listing_service import ListingService
from inference_storefront.services.system_service import SystemService
from inference_storefront.lifecycle_steps import register_inference_lifecycle_steps
from inference_storefront.startup import _startup_tasks
from inference_storefront.settlement_composition import (
    InferenceSettlementComposition,
    build_inference_settlement_composition,
    build_storefront_settlement_registry,
)
from inference_storefront.utils.config import (
    AGENT_ID,
    BASE_URL_OVERRIDE,
    CHAINS,
    resolve_admin_identities,
    resolve_identity_signer,
    resolve_registry_authorities,
    settings,
    settlement_config_mapping,
)
from inference_storefront.utils.sqlite_client import get_sqlite_client
from market_storefront_kit import (
    StorefrontLoopController,
)

logger = logging.getLogger(__name__)

def run_serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    """Launch uvicorn. Called by ``inference-storefront serve``."""
    import uvicorn

    resolved_port = port if port is not None else settings.port
    uvicorn.run(
        app,
        host=host,
        port=resolved_port,
        root_path=settings.gateway.root_path,
    )


@dataclass(frozen=True, slots=True)
class InferenceStorefrontServices:
    """Lifespan-owned inference services bound to one domain contract."""

    domain: MarketDomainContract
    sqlite_client: Any
    marketplace_signer: Any
    alkahest_clients: dict[str, Any]
    settlement_repository: Any
    settlement_runtime: Any
    settlement_worker: Any
    settlement_coordinator: Any
    settlement_composition: InferenceSettlementComposition
    issuance_evidence_service: Any
    private_result_repository: Any
    failure_policy: Any
    listing_service: Any
    negotiation_runtime: Any
    negotiation_service: Any
    system_service: Any


def _build_alkahest_clients() -> dict[str, Any]:
    private_key = (settings.wallet.private_key or "").strip()
    missing = () if private_key else ("wallet.private_key",)
    return build_alkahest_clients(
        AlkahestClientPolicy(
            private_key=private_key,
            chains=tuple(
                AlkahestChain(
                    name=name,
                    rpc_url=chain.rpc_url,
                    address_config_path=chain.alkahest_address_config_path,
                )
                for name, chain in CHAINS.items()
            ),
            missing_requirements=missing,
            warn_if_no_chains=True,
        ),
        logger=logger,
    )


def _build_inference_services(
    domain: MarketDomainContract,
) -> InferenceStorefrontServices:
    marketplace_signer = resolve_identity_signer()
    resolve_admin_identities()
    if settings.enable_registry_discovery:
        resolve_registry_authorities()
    settlement_registry = build_storefront_settlement_registry()
    settlement_config = settlement_registry.resolve(
        settlement_config_mapping(),
        role="seller",
    )
    alkahest_section = settlement_config.mechanism_config("alkahest")
    alkahest_enabled = bool(
        alkahest_section is not None and getattr(alkahest_section, "enabled", False)
    )
    if alkahest_enabled:
        alkahest_clients = _build_alkahest_clients()
    else:
        alkahest_clients = {}
    sqlite_client = get_sqlite_client(
        local_listing_principal=marketplace_signer.identity,
        expected_legacy_sellers=(BASE_URL_OVERRIDE,),
    )
    set_stage_event_db_path(sqlite_client.db_path)
    failure_policy = build_inference_failure_policy()
    settlement_composition = build_inference_settlement_composition(
        domain=domain,
        sqlite_client=sqlite_client,
        alkahest_clients=alkahest_clients,
        marketplace_signer=marketplace_signer,
        failure_policy=failure_policy,
    )
    negotiation_runtime = build_inference_negotiation_runtime(
        domain,
        accepted_obligation_dispatch=(
            settlement_composition.accepted_obligation_dispatch()
        ),
        settlement_artifacts_builder=settlement_composition.accepted_settlement_artifacts,
    )
    settlement_runtime = settlement_composition.runtime
    settlement_worker = settlement_composition.worker
    settlement_repository = settlement_composition.repository
    settlement_coordinator = SettlementJobCoordinator(
        settlement_runtime,
        prepare=partial(
            prepare_inference_settlement,
            sqlite_client=sqlite_client,
            local_principal=marketplace_signer.identity,
            composition=settlement_composition,
        ),
        reserve_start=partial(
            reserve_inference_settlement,
            sqlite_client,
            settlement_runtime=settlement_runtime,
            wake_servicing=settlement_worker.wake,
        ),
        fulfill=fulfill_inference_settlement,
        persist_outcome=partial(
            persist_inference_settlement_outcome,
            sqlite_client,
        ),
        wake_servicing=settlement_worker.wake,
    )
    return InferenceStorefrontServices(
        domain=domain,
        sqlite_client=sqlite_client,
        marketplace_signer=marketplace_signer,
        alkahest_clients=alkahest_clients,
        settlement_repository=settlement_repository,
        settlement_runtime=settlement_runtime,
        settlement_worker=settlement_worker,
        settlement_coordinator=settlement_coordinator,
        settlement_composition=settlement_composition,
        issuance_evidence_service=settlement_composition.evidence_service,
        private_result_repository=settlement_composition.private_results,
        failure_policy=failure_policy,
        listing_service=ListingService(
            sqlite_client=sqlite_client,
            seller_principal=marketplace_signer.identity,
            settlement_composition=settlement_composition,
        ),
        negotiation_runtime=negotiation_runtime,
        negotiation_service=NegotiationService(
            sqlite_client=sqlite_client,
            continue_negotiation=negotiation_runtime.continue_negotiation,
            stage_event=stage_event,
        ),
        system_service=SystemService(
            sqlite_client=sqlite_client,
            agent_id=AGENT_ID,
        ),
    )


async def _start_inference_services(
    services: InferenceStorefrontServices,
) -> None:

    _container.resolved_market_domain = services.domain
    _container.resolved_sqlite_client = services.sqlite_client
    _container.resolved_alkahest_clients = services.alkahest_clients
    _container.resolved_settlement_repository = services.settlement_repository
    _container.resolved_settlement_runtime = services.settlement_runtime
    _container.resolved_settlement_worker = services.settlement_worker
    _container.resolved_settlement_coordinator = services.settlement_coordinator
    _container.resolved_settlement_composition = services.settlement_composition
    _container.resolved_issuance_evidence_service = services.issuance_evidence_service
    _container.resolved_private_result_repository = services.private_result_repository
    _container.resolved_marketplace_signer = services.marketplace_signer
    _container.resolved_failure_policy = services.failure_policy
    _container.resolved_listing_service = services.listing_service
    _container.resolved_negotiation_runtime = services.negotiation_runtime
    _container.resolved_negotiation_service = services.negotiation_service
    _container.resolved_system_service = services.system_service
    loops = StorefrontLoopController(logger=logger)
    register_inference_lifecycle_steps(loops)
    _container.resolved_loop_controller = loops
    logger.info("[STARTUP] Singletons initialized")
    await _startup_tasks(domain=services.domain)
    logger.info("[STARTUP] Background tasks started")


async def _stop_inference_services(
    services: InferenceStorefrontServices,
) -> None:
    _container.clear_lifespan_state(domain=services.domain)
    _container.resolved_negotiation_runtime = None
    logger.info("[SHUTDOWN] inference storefront shutting down")


from inference_storefront.controllers.lifecycle_controller import (  # noqa: E402
    router as lifecycle_router,
)
from inference_storefront.controllers.listings_controller import (  # noqa: E402
    router as listings_router,
)
from inference_storefront.controllers.negotiate_controller import (  # noqa: E402
    router as negotiate_router,
)
from inference_storefront.controllers.negotiations_controller import (  # noqa: E402
    router as negotiations_router,
)
from inference_storefront.controllers.settle_controller import (  # noqa: E402
    admin_settle_router,
)
from inference_storefront.controllers.settle_controller import (  # noqa: E402
    router as settle_router,
)
from inference_storefront.controllers.settle_controller import (  # noqa: E402
    settlements_router,
)
from inference_storefront.controllers.system_controller import (  # noqa: E402
    router as system_router,
)
from inference_storefront.controllers.trading_pause_controller import (  # noqa: E402
    router as trading_pause_router,
)


def build_inference_storefront_registry(
    *,
    domain: MarketDomainContract,
) -> StorefrontDomainRegistry:
    """Build the explicit one-registration inference storefront registry."""

    return StorefrontDomainRegistry((inference_registration(domain),))


def build_inference_storefront_app(
    *,
    registry: StorefrontDomainRegistry,
) -> Any:
    """Build the inference app from one frozen domain registration."""

    registration = registry.resolve_mode("inference")
    domain = registration.contract

    def build_services(selected: MarketDomainContract) -> InferenceStorefrontServices:
        if selected is not domain:
            raise RuntimeError(
                "storefront kit supplied a domain outside the inference registration"
            )
        return _build_inference_services(selected)

    return build_composed_storefront_app(
        StorefrontComposition(
            registry=registry,
            binding=registration.binding,
            domain=domain,
            app=StorefrontAppConfig(
                title="Arkhai Inference Storefront",
                description=(
                    "Seller-side storefront for the Arkhai inference "
                    "marketplace.\n\n"
                    "Admin and authenticated endpoints require the shared "
                    "scheme-tagged marketplace request-signature version 2 headers."
                ),
                version="1.0.0",
                root_path=settings.gateway.root_path,
                swagger_ui_parameters={"persistAuthorization": True},
            ),
            services=StorefrontServiceHooks(
                build=build_services,
                start=_start_inference_services,
                stop=_stop_inference_services,
            ),
            routes=StorefrontRouteHooks(
                routers=(
                    system_router,
                    listings_router,
                    negotiate_router,
                    negotiations_router,
                    settle_router,
                    settlements_router,
                    admin_settle_router,
                    lifecycle_router,
                    trading_pause_router,
                ),
                middleware=(authenticate_response,),
            ),
        )
    )


app = build_inference_storefront_app(
    registry=build_inference_storefront_registry(
        domain=get_market_domain_contract(),
    )
)
