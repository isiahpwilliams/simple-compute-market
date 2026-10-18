"""The storefront client's signed operations agree with the service's table.

The credits service recomputes the operation and the signed resource from
the route it matched, then verifies the caller's signature over *its* own
values. A client that names an operation the service spells differently, or
signs a resource the service derives from somewhere else, does not produce
a slightly wrong request -- it produces a signature that cannot verify, on
every call to that route. Two tables therefore have to stay identical:

- `CREDITS_ROUTE_CONTRACTS` (the service, authoritative),
- `arkhai_inference.settlement.credits_client` (the storefront, `seller`).

The gateway's gate signs in the `service` role against the same table; its
client is compared here once the gateway package exists.

Lives in the service's own suite because the service owns the authoritative
table, and because the client it compares against needs `fastapi` and
`market_site` -- which the service has and the domain package deliberately
does not.
"""

from __future__ import annotations

import pytest

from inference_service.middleware.route_contracts import CREDITS_ROUTE_CONTRACTS


@pytest.fixture(scope="module")
def contracts():
    return {c.operation: c for c in CREDITS_ROUTE_CONTRACTS}


def test_storefront_operations_exist_and_admit_the_seller_role(contracts):
    """The storefront's operations, signed as `seller`."""
    from arkhai_inference.settlement import credits_client as sf

    keyed = {
        sf.ISSUANCE_GET_OPERATION: "fulfillment_id",
        sf.KEY_GET_OPERATION: "key_id",
        sf.KEY_REVOKE_OPERATION: "key_id",
        sf.KEY_ADJUST_OPERATION: "key_id",
        sf.KEY_GRANTS_LIST_OPERATION: "key_id",
        sf.KEY_USAGE_LIST_OPERATION: "key_id",
        sf.KEYS_LIST_OPERATION: None,
    }
    for operation, path_resource in keyed.items():
        assert operation in contracts, sorted(contracts)
        contract = contracts[operation]
        assert sf.STOREFRONT_ROLE in contract.allowed_roles, operation
        assert contract.path_resource == path_resource, operation


def test_issuance_signs_the_optional_body_resource(contracts):
    """`credits_issue` takes its resource from the body, optionally.

    The client mirrors that by signing the body's `fulfillment_id` or the
    empty string. Pinned because it is the one operation whose resource is
    not a path segment, so it is the one most likely to be "fixed" into
    signing something else.
    """
    from arkhai_inference.settlement import credits_client as sf

    contract = contracts[sf.ISSUE_OPERATION]
    assert sf.STOREFRONT_ROLE in contract.allowed_roles
    assert contract.body_resource == "fulfillment_id"
    assert contract.optional_body_resource is True
    assert getattr(contract, "path_resource", None) is None
