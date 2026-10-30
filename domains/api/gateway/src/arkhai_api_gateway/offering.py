"""The one value a gateway is configured with.

A domain's executable validates its own listing and projects it to a
`GatewayOffering`; the library reads nothing else, so it learns no domain's
listing schema.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arkhai_api_gate import GateConfig, PurchasePointer


@dataclass(frozen=True, kw_only=True)
class GatewayOffering:
    """What one gateway deployment serves and how it charges.

    ``service`` is the one name admitted in a request's ``model`` and the only
    entry of the model list. ``scope_service`` and ``scope_resource_id`` are the
    offering a key must have been issued for, which the authority enforces.
    ``default_charge`` is charged only when a key's verification pins no
    charge of its own. ``upstream_base_url`` is the model server's OpenAI base
    URL, the one its ``/chat/completions`` is under, and
    ``upstream_credential_file`` the mounted secret the gateway presents to it,
    if it requires one. ``current_terms`` is the offering's current canonical
    terms, handed to the verification hook.
    """

    service: str
    scope_service: str | None
    scope_resource_id: str | None
    default_charge: int
    purchase: PurchasePointer
    upstream_base_url: str
    upstream_credential_file: Path | None = None
    # A mapping is unhashable, so the terms are left out of the offering's hash.
    current_terms: Mapping[str, Any] | None = field(default=None, hash=False)

    def __post_init__(self) -> None:
        if not self.service:
            raise ValueError("a gateway offering names the service it admits")
        if self.default_charge < 0:
            raise ValueError("a gateway offering's default charge is non-negative")

    def gate_config(self, base: GateConfig) -> GateConfig:
        """``base`` with this offering's scope, default charge, and purchase pointer.

        The gate is configured from the offering rather than beside it, so the
        scope verification sends and the charge it falls back to cannot differ
        from what the gateway admits.
        """
        return dataclasses.replace(
            base,
            scope_service=self.scope_service,
            scope_resource_id=self.scope_resource_id,
            amount_per_request=self.default_charge,
            purchase=self.purchase,
        )


def read_upstream_credential(path: Path) -> str:
    """The credential in a mounted secret file, stripped of a trailing newline.

    A mounted secret is routinely group-readable, so its mode is not checked;
    it must be a regular, non-empty file.
    """
    try:
        if not path.is_file():
            raise ValueError("the upstream credential file must be a regular file")
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError("the upstream credential file cannot be read") from exc
    if not value:
        raise ValueError("the upstream credential file is empty")
    return value
