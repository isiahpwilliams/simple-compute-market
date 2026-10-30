"""Configuration the storefront refuses to start under.

Checked before the signer, database, or any loop starts, so a malformed
capacity site, poll interval, or `[settlement].priority` cannot stop startup
partway, and every problem is reported together under its heading.
"""

from __future__ import annotations

from dynaconf import Dynaconf

from inference_storefront.container import SELLER_STAGES
from inference_storefront.utils.config import (
    capacity_poll_interval,
    configured_site_ids,
    settlement_config_mapping,
)

CAPACITY_HEADING = "the storefront cannot read its capacity configuration"
MECHANISM_HEADING = "the storefront is configured for a settlement mechanism it does not compose"


class StorefrontStartupError(RuntimeError):
    """The storefront's configuration states a setting it cannot read or honour."""


def capacity_configuration_problems() -> list[str]:
    """Why the configured capacity sites or poll interval cannot be read."""
    problems: list[str] = []
    try:
        configured_site_ids()
    except RuntimeError as exc:
        problems.append(str(exc))
    try:
        capacity_poll_interval()
    except ValueError as exc:
        problems.append(str(exc))
    return problems


def mechanism_configuration_problems(source: Dynaconf | None = None) -> list[str]:
    """Each `[settlement].priority` mechanism that no composed stage settles."""
    try:
        priority = settlement_config_mapping(source).get("priority") or []
    except ValueError as exc:
        return [str(exc)]
    if not isinstance(priority, list):
        return ["[settlement].priority must be a list of mechanism identifiers"]
    composed = ", ".join(sorted(SELLER_STAGES))
    return [
        f"[settlement].priority names {mechanism!r}; this storefront settles only through {composed}"
        for mechanism in priority
        if mechanism not in SELLER_STAGES
    ]


def require_startable_storefront(source: Dynaconf | None = None) -> None:
    """Refuse to start, naming each problem under its heading."""
    sections = [
        f"{heading}: " + "; ".join(problems)
        for heading, problems in (
            (CAPACITY_HEADING, capacity_configuration_problems()),
            (MECHANISM_HEADING, mechanism_configuration_problems(source)),
        )
        if problems
    ]
    if sections:
        raise StorefrontStartupError(". ".join(sections))


__all__ = [
    "CAPACITY_HEADING",
    "MECHANISM_HEADING",
    "StorefrontStartupError",
    "capacity_configuration_problems",
    "mechanism_configuration_problems",
    "require_startable_storefront",
]
