"""The storefront's startup preflight: the inference authority must answer, and accept this storefront, before trading starts."""

from __future__ import annotations

import asyncio
import logging

import httpx
from arkhai_api_client import AuthorityAuthenticationError, AuthorityClient

from inference_storefront.services.credits_service_client import get_credits_service_client
from inference_storefront.utils import config
from inference_storefront.utils.config import settings

logging.basicConfig(
    level=getattr(logging, str(settings.get("log_level", "INFO")).upper(), logging.INFO)
)

logger = logging.getLogger(__name__)

# A key id no authority issues: the seller-only key read is side-effect-free
# and answers an unknown key with a signed 404, so it proves both directions of
# authentication without touching any record.
PREFLIGHT_PROBE_KEY_ID = "storefront-preflight-probe"


class AuthorityAuthenticationRefused(RuntimeError):
    """The inference authority answered but refused this storefront, or could not be verified."""


async def _probe_authentication(client: AuthorityClient, url: str) -> None:
    """Refuse at once when the authority rejects the signed call or its answer does not verify.

    A signed server error or a transport failure propagates to the retry loop;
    an unsigned answer, such as a proxy's error page, fails verification and
    refuses.
    """
    try:
        await client.get_key(PREFLIGHT_PROBE_KEY_ID)
    except AuthorityAuthenticationError as exc:
        raise AuthorityAuthenticationRefused(
            f"[STARTUP] Inference authority at {url} answered without a verifiable "
            f"signature from [credits.expected_authorities] ({exc})."
        ) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise AuthorityAuthenticationRefused(
                f"[STARTUP] Inference authority at {url} refused this storefront's "
                f"signed call (HTTP {exc.response.status_code}); it must trust the "
                "storefront's marketplace identity in the seller role."
            ) from exc
        raise


async def preflight_credits_service(client: AuthorityClient | None = None) -> None:
    """Block startup until the inference authority accepts a signed probe, or give up.

    The signed probe is the whole check, so nothing unsigned can stand in for
    it. Only a transport outage lasting the whole timeout may be excused by
    ``[credits].fail_on_unreachable``; an authority that answered and never
    accepted the probe always stops startup, and a refusal stops it at once.
    """
    url = config.credits_service_url()
    if not url:
        raise RuntimeError(
            "[STARTUP] [credits].service_url is not configured — the "
            "storefront has nothing to sell for."
        )
    timeout_s = max(int(settings.get("credits.preflight_timeout", 30)), 1)
    deadline = asyncio.get_event_loop().time() + timeout_s
    last_error: str | None = None
    answered = False

    while True:
        try:
            await _probe_authentication(client or get_credits_service_client(), url)
            logger.info("[STARTUP] Inference authority reachable at %s", url)
            return
        except AuthorityAuthenticationRefused:
            raise
        except httpx.TransportError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            answered = True
            last_error = f"{type(exc).__name__}: {exc}"

        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        await asyncio.sleep(min(2.0, remaining))

    if answered:
        raise RuntimeError(
            f"[STARTUP] Inference authority at {url} answered but did not accept "
            f"the signed probe within {timeout_s}s ({last_error})."
        )
    msg = (
        f"[STARTUP] Inference authority at {url} unreachable after {timeout_s}s "
        f"({last_error})."
    )
    if settings.get("credits.fail_on_unreachable", True):
        raise RuntimeError(
            msg + " Set [credits].fail_on_unreachable = false to start the "
            "storefront anyway (issuance will fail until it is reachable)."
        )
    logger.error(msg + " Continuing because fail_on_unreachable=false.")
