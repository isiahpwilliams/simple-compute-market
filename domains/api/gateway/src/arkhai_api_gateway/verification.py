"""The per-request verification hook.

It runs after the key is verified and before it is charged, so a refusal costs
the buyer nothing. It receives the offering's current canonical terms and the
key's accepted terms and digest as verification returned them, so a proof
format can detect a change since acceptance or verify against the accepted
terms themselves. No proof format is defined here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class VerificationRefusal:
    """Why a hook refused a request: the HTTP status and a machine-readable error code."""

    status: int
    error: str


class VerificationHook(Protocol):
    """Asynchronous, since a proof format may need to fetch what it verifies against."""

    async def __call__(
        self,
        current_terms: Mapping[str, Any] | None,
        accepted_terms: Mapping[str, Any] | None,
        terms_digest: str | None,
    ) -> VerificationRefusal | None: ...


async def admit_all(
    current_terms: Mapping[str, Any] | None,
    accepted_terms: Mapping[str, Any] | None,
    terms_digest: str | None,
) -> VerificationRefusal | None:
    """The default hook: admits every verified key."""
    return None
