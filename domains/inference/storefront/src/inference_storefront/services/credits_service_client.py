"""Storefront-owned composition of the family authority client."""

from __future__ import annotations

from arkhai_api_client import AuthorityClient
from arkhai_inference.label import INFERENCE_LABEL

from inference_storefront.utils import config

_client: AuthorityClient | None = None


def get_credits_service_client() -> AuthorityClient:
    """Return the process-wide client for the configured inference authority.

    Every request is signed with the marketplace identity and every response
    verified against the configured authority trust set; the authority accepts
    nothing else. Startup refuses a storefront missing either.
    """
    global _client
    if _client is None:
        _client = AuthorityClient(
            config.credits_service_url(),
            label=INFERENCE_LABEL,
            signer=config.resolve_identity_signer(),
            expected_authorities=config.credits_expected_authorities(),
        )
    return _client
