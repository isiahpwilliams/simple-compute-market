"""Batched-flush behavior, the ASGI binding, and the verify cache's tie to the secret.

The synchronous decision table is pinned by the conformance session;
these cover what is outside it: the optimistic batched charge path
(timing-dependent, so impl-local), the ASGI adapter end to end, and a
cached verification answering only for the secret that earned it.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from arkhai_api_gate.client import ConsumeResult, TokensClient, VerifyResult
from arkhai_api_gate.config import GateConfig, PurchasePointer
from arkhai_api_gate.gate import TokenGate, VerifiedKey
from arkhai_api_gate.asgi import TokenGateMiddleware


class FakeClient:
    """Records calls and returns canned results — for batch-vs-sync asserts."""

    def __init__(self, *, balance: int) -> None:
        self._balance = balance
        self.verify_calls = 0
        self.consume_calls: list[dict] = []
        self.batch_calls: list[list[dict]] = []

    async def verify(self, *, key_id: str, secret: str, service=None, resource_id=None) -> VerifyResult:
        self.verify_calls += 1
        return VerifyResult(valid=True, status="active", balance=self._balance)

    async def consume(self, *, key_id, amount, idempotency_key=None, service=None, resource_id=None) -> ConsumeResult:
        self.consume_calls.append({"key_id": key_id, "amount": amount})
        self._balance = max(0, self._balance - amount)
        if self._balance < 0:
            return ConsumeResult(ok=False, balance=0, reason="insufficient_credits")
        return ConsumeResult(ok=True, balance=self._balance, consumed=amount)

    async def consume_batch(self, items) -> list[ConsumeResult]:
        self.batch_calls.append(list(items))
        out = []
        for item in items:
            self._balance = max(0, self._balance - item["amount"])
            out.append(ConsumeResult(ok=True, balance=self._balance, consumed=item["amount"]))
        return out


def _cfg(**kw) -> GateConfig:
    base = dict(
        service_url="http://svc", authority_label="test-authority", amount_per_request=1,
        flush_interval_seconds=0.0, low_balance_threshold=0,
        purchase=PurchasePointer(listing_id="lst-1"),
    )
    base.update(kw)
    return GateConfig(**base)


async def test_batched_charges_accumulate_then_flush_once():
    client = FakeClient(balance=10)
    gate = TokenGate(_cfg(flush_interval_seconds=60.0, low_balance_threshold=1), client)

    for _ in range(3):
        d = await gate.authorize("Bearer ak_live.s")
        assert d.allowed
    # Comfortably above threshold → no synchronous consume yet.
    assert client.consume_calls == []
    assert client.verify_calls == 1  # verify cached after the first

    await gate.flush()
    assert len(client.batch_calls) == 1
    assert len(client.batch_calls[0]) == 3


async def test_charge_goes_synchronous_near_exhaustion():
    client = FakeClient(balance=3)
    # threshold 2: a charge that would leave <= 2 estimated is synchronous.
    gate = TokenGate(_cfg(flush_interval_seconds=60.0, low_balance_threshold=2), client)

    d = await gate.authorize("Bearer ak_live.s")  # 3 -> est 2 <= 2 => sync
    assert d.allowed
    assert len(client.consume_calls) == 1
    assert client.batch_calls == []


async def test_asgi_allows_valid_and_402s_exhausted():
    # A trivial downstream ASGI app the gate fronts.
    async def app(scope, receive, send):
        assert scope["type"] == "http"
        body = b'{"forecast":"sunny"}'
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": body})

    # Scripted credits service: valid key, one credit then exhausted.
    state = {"balance": 1}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/verify"):
            return httpx.Response(200, json={
                "valid": True, "status": "active", "balance": state["balance"],
            })
        # consume
        if state["balance"] >= 1:
            state["balance"] -= 1
            return httpx.Response(200, json={"ok": True, "consumed": 1, "balance": state["balance"]})
        return httpx.Response(402, json={"error": "insufficient_credits", "balance": 0})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TokensClient(service_url="http://svc", http=http)
    gate = TokenGate(_cfg(purchase=PurchasePointer(listing_id="lst-1", storefront_url="http://sf")), client)
    gated = TokenGateMiddleware(app, gate=gate)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gated), base_url="http://app",
    ) as c:
        r1 = await c.get("/api/forecast", headers={"Authorization": "Bearer ak_live.s"})
        assert r1.status_code == 200
        assert r1.json() == {"forecast": "sunny"}

        r2 = await c.get("/api/forecast", headers={"Authorization": "Bearer ak_live.s"})
        assert r2.status_code == 402
        body = r2.json()
        assert body["error"] == "insufficient_credits"
        assert body["purchase"]["listing_id"] == "lst-1"

        # Health is excluded — served without a token.
        r3 = await c.get("/health")
        # The trivial app answers everything 200; the point is no 401.
        assert r3.status_code == 200

    await http.aclose()


async def test_asgi_missing_key_is_401():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={"valid": True, "status": "active", "balance": 5})
    ))
    client = TokensClient(service_url="http://svc", http=http)
    gate = TokenGate(_cfg(), client)
    gated = TokenGateMiddleware(app, gate=gate)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gated), base_url="http://app",
    ) as c:
        r = await c.get("/api/forecast")
        assert r.status_code == 401
        assert r.json()["error"] == "missing_api_key"
    await http.aclose()


class SecretCheckingClient:
    """An authority that accepts only the secrets it was given, recording what it was asked."""

    def __init__(self, *accepted: str) -> None:
        self.accepted = set(accepted)
        self.verified: list[str] = []
        self.consumed = 0

    async def verify(self, *, key_id: str, secret: str, service=None, resource_id=None) -> VerifyResult:
        self.verified.append(secret)
        if secret in self.accepted:
            return VerifyResult(valid=True, status="active", balance=10)
        return VerifyResult(valid=False, status=None, balance=0)

    async def consume(self, *, key_id, amount, idempotency_key=None, service=None, resource_id=None) -> ConsumeResult:
        self.consumed += 1
        return ConsumeResult(ok=True, balance=10 - self.consumed, consumed=amount)


async def test_a_cached_key_does_not_admit_a_different_secret():
    client = SecretCheckingClient("ak_victim.real")
    gate = TokenGate(_cfg(), client)

    assert (await gate.authorize("Bearer ak_victim.real")).allowed
    forged = await gate.authorize("Bearer ak_victim.forged")

    assert (forged.allowed, forged.status, forged.body) == (False, 401, {"error": "invalid_api_key"})
    assert client.verified == ["ak_victim.real", "ak_victim.forged"]
    assert client.consumed == 1


async def test_a_refused_secret_leaves_the_cached_verification_in_place():
    client = SecretCheckingClient("ak_victim.real")
    gate = TokenGate(_cfg(), client)

    await gate.authorize("Bearer ak_victim.real")
    await gate.authorize("Bearer ak_victim.forged")

    assert (await gate.authorize("Bearer ak_victim.real")).allowed
    assert client.verified == ["ak_victim.real", "ak_victim.forged"]


async def test_a_rotated_secret_the_authority_accepts_replaces_the_cached_one():
    client = SecretCheckingClient("ak_k.first", "ak_k.rotated")
    gate = TokenGate(_cfg(), client)

    await gate.authorize("Bearer ak_k.first")
    assert (await gate.authorize("Bearer ak_k.rotated")).allowed
    assert (await gate.authorize("Bearer ak_k.rotated")).allowed
    await gate.authorize("Bearer ak_k.first")

    assert client.verified == ["ak_k.first", "ak_k.rotated", "ak_k.first"]


class HeldVerificationClient(SecretCheckingClient):
    """Holds the first verification of one secret, answering it valid, until the test releases it."""

    def __init__(self, held: str, *accepted: str) -> None:
        super().__init__(*accepted)
        self.held = held
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def verify(self, *, key_id: str, secret: str, service=None, resource_id=None) -> VerifyResult:
        if secret != self.held or self.started.is_set():
            return await super().verify(key_id=key_id, secret=secret)
        self.verified.append(secret)
        self.started.set()
        await self.release.wait()
        return VerifyResult(valid=True, status="active", balance=10)


async def _hold_old_secret(gate: TokenGate, client: HeldVerificationClient) -> asyncio.Future:
    old = asyncio.ensure_future(gate.authorize("Bearer ak_k.old"))
    await asyncio.wait_for(client.started.wait(), timeout=5)
    return old


@pytest.mark.parametrize("clock", [time.monotonic, lambda: 100.0], ids=["monotonic", "frozen"])
async def test_a_late_answer_for_an_older_secret_does_not_replace_a_newer_one(clock):
    client = HeldVerificationClient("ak_k.old", "ak_k.new")
    gate = TokenGate(_cfg(), client, clock=clock)

    old = await _hold_old_secret(gate, client)
    assert (await gate.authorize("Bearer ak_k.new")).allowed
    client.release.set()
    # The gate now holds the newer secret's verification, so the late one is not charged.
    late = await asyncio.wait_for(old, timeout=5)
    assert (late.allowed, late.status) == (False, 401)

    again = await gate.authorize("Bearer ak_k.old")

    assert (again.allowed, again.status) == (False, 401)
    assert client.verified == ["ak_k.old", "ak_k.new", "ak_k.old"]


@pytest.mark.parametrize("clock", [time.monotonic, lambda: 100.0], ids=["monotonic", "frozen"])
async def test_a_late_answer_does_not_outlast_a_newer_refusal_of_the_same_secret(clock):
    client = HeldVerificationClient("ak_k.old", "ak_k.new")
    gate = TokenGate(_cfg(), client, clock=clock)

    assert (await gate.authorize("Bearer ak_k.new")).allowed
    old = await _hold_old_secret(gate, client)
    assert not (await gate.authorize("Bearer ak_k.old")).allowed
    client.release.set()
    await asyncio.wait_for(old, timeout=5)

    again = await gate.authorize("Bearer ak_k.old")

    assert (again.allowed, again.status) == (False, 401)
    assert client.verified == ["ak_k.new", "ak_k.old", "ak_k.old", "ak_k.old"]


# Verification and charge as separable steps


class ScriptedClient:
    """Answers verify with a scripted result and records every call with its arguments."""

    def __init__(self, verify: VerifyResult, *, consume: ConsumeResult | None = None) -> None:
        self._verify = verify
        self._consume = consume
        self.calls: list[tuple[str, dict]] = []

    async def verify(self, **kwargs) -> VerifyResult:
        self.calls.append(("verify", kwargs))
        return self._verify

    async def consume(self, **kwargs) -> ConsumeResult:
        self.calls.append(("consume", kwargs))
        return self._consume or ConsumeResult(ok=True, balance=self._verify.balance - kwargs["amount"], consumed=kwargs["amount"])

    async def consume_batch(self, items) -> list[ConsumeResult]:
        self.calls.append(("consume_batch", {"items": list(items)}))
        return [ConsumeResult(ok=True, balance=0, consumed=item["amount"]) for item in items]


PINNED = VerifyResult(
    valid=True, status="active", balance=50,
    accepted_terms={"rate_card": {}}, terms_digest="sha256:" + "a" * 64, request_charge=3,
)


async def test_verification_alone_makes_no_charge():
    client = ScriptedClient(PINNED)
    gate = TokenGate(_cfg(), client)

    verified = await gate.verify("Bearer ak_live.s")

    assert verified.key_id == "ak_live"
    assert (verified.accepted_terms, verified.terms_digest, verified.request_charge) == (
        PINNED.accepted_terms, PINNED.terms_digest, 3,
    )
    assert [name for name, _ in client.calls] == ["verify"]


@pytest.mark.parametrize("batched", [False, True], ids=["synchronous", "batched"])
async def test_verify_then_charge_makes_the_same_exchanges_and_state_as_authorize(batched):
    config = _cfg(flush_interval_seconds=60.0, low_balance_threshold=1) if batched else _cfg()
    separate, together = ScriptedClient(PINNED), ScriptedClient(PINNED)
    gate_a, gate_b = TokenGate(config, separate), TokenGate(config, together)

    for idem in ("idem-1", "idem-2"):
        decision_a = await gate_a.charge(await gate_a.verify("Bearer ak_live.s"), idempotency_key=idem)
        decision_b = await gate_b.authorize("Bearer ak_live.s", idempotency_key=idem)
        assert decision_a == decision_b
    await gate_a.flush()
    await gate_b.flush()

    # The second request is answered from the cached verification in both.
    assert separate.calls == together.calls
    assert [name for name, _ in separate.calls].count("verify") == 1


@pytest.mark.parametrize(
    ("verified", "charged"),
    [(PINNED, 3), (VerifyResult(valid=True, status="active", balance=50), 2)],
    ids=["pinned-charge", "configured-default"],
)
async def test_the_charge_is_the_verified_one_and_the_configured_amount_otherwise(verified, charged):
    client = ScriptedClient(verified)
    gate = TokenGate(_cfg(amount_per_request=2), client)

    assert (await gate.authorize("Bearer ak_live.s")).allowed
    assert client.calls[-1][1]["amount"] == charged


@pytest.mark.parametrize(
    ("scope", "sent"),
    [
        ({"scope_service": "svc", "scope_resource_id": "quota"}, {"service": "svc", "resource_id": "quota"}),
        ({}, {"service": None, "resource_id": None}),
    ],
    ids=["scoped", "unscoped"],
)
async def test_the_configured_scope_is_sent_on_verify_and_consume(scope, sent):
    client = ScriptedClient(PINNED)
    gate = TokenGate(_cfg(**scope), client)

    await gate.authorize("Bearer ak_live.s")

    for name, kwargs in client.calls:
        assert {key: kwargs[key] for key in ("service", "resource_id")} == sent, name


async def test_a_pinned_charge_is_batched_and_requeued_at_its_own_amount():
    client = ScriptedClient(PINNED)
    gate = TokenGate(_cfg(flush_interval_seconds=60.0, low_balance_threshold=1, scope_service="svc"), client)

    assert (await gate.authorize("Bearer ak_live.s")).allowed

    async def unavailable(items):
        client.calls.append(("consume_batch", {"items": list(items)}))
        return [ConsumeResult(ok=False, balance=0, reason="batch_unavailable") for _ in items]

    client.consume_batch = unavailable
    await gate.flush()
    await gate.flush()
    batches = [kwargs["items"] for name, kwargs in client.calls if name == "consume_batch"]
    assert [[item["amount"] for item in batch] for batch in batches] == [[3], [3]]


async def test_charging_a_key_the_gate_never_verified_is_an_invalid_key():
    decision = await TokenGate(_cfg(), ScriptedClient(PINNED)).charge(VerifiedKey(key_id="ak_other"))
    assert (decision.allowed, decision.status) == (False, 401)


async def test_a_key_out_of_scope_is_403_and_never_charged():
    client = ScriptedClient(VerifyResult(valid=False, status="key_out_of_scope", balance=0))
    gate = TokenGate(_cfg(scope_service="svc"), client)

    decision = await gate.authorize("Bearer ak_live.s")

    assert (decision.allowed, decision.status, decision.body["error"]) == (False, 403, "key_out_of_scope")
    assert [name for name, _ in client.calls] == ["verify"]


async def test_a_consume_refused_out_of_scope_is_403():
    client = ScriptedClient(PINNED, consume=ConsumeResult(ok=False, balance=0, reason="key_out_of_scope"))
    gate = TokenGate(_cfg(scope_service="svc"), client)

    decision = await gate.authorize("Bearer ak_live.s")

    assert (decision.allowed, decision.status, decision.body["error"]) == (False, 403, "key_out_of_scope")


async def test_a_batched_item_carries_the_configured_scope():
    client = ScriptedClient(PINNED)
    gate = TokenGate(
        _cfg(flush_interval_seconds=60.0, low_balance_threshold=1, scope_service="svc", scope_resource_id="quota"),
        client,
    )

    assert (await gate.authorize("Bearer ak_live.s", idempotency_key="idem-1")).allowed
    await gate.flush()

    assert client.calls[-1] == ("consume_batch", {"items": [
        {"key_id": "ak_live", "amount": 3, "idempotency_key": "idem-1", "service": "svc", "resource_id": "quota"},
    ]})


async def test_a_batched_item_refused_out_of_scope_denies_the_key_from_then_on():
    client = ScriptedClient(PINNED)
    gate = TokenGate(_cfg(flush_interval_seconds=60.0, low_balance_threshold=1, scope_service="svc"), client)
    assert (await gate.authorize("Bearer ak_live.s")).allowed
    verified = await gate.verify("Bearer ak_live.s")

    async def out_of_scope(items):
        return [ConsumeResult(ok=False, balance=0, reason="key_out_of_scope") for _ in items]

    client.consume_batch = out_of_scope
    await gate.flush()
    decision = await gate.charge(verified)

    assert (decision.allowed, decision.status, decision.body["error"]) == (False, 403, "key_out_of_scope")
    assert [name for name, _ in client.calls] == ["verify"]


# A verified key is charged only while the gate's verification still admits it


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _batched_gate(client, clock: Clock) -> TokenGate:
    return TokenGate(_cfg(flush_interval_seconds=60.0, low_balance_threshold=1, verify_ttl_seconds=30.0), client, clock=clock)


async def test_a_key_revoked_between_verify_and_charge_is_refused_and_never_charged():
    clock, client = Clock(), ScriptedClient(PINNED)
    gate = _batched_gate(client, clock)
    verified = await gate.verify("Bearer ak_live.s")

    # Another request re-verifies the key after its verification expired and finds it revoked.
    clock.now += 31
    client._verify = VerifyResult(valid=False, status="revoked", balance=50)
    assert (await gate.verify("Bearer ak_live.s")).status == 403
    decision = await gate.charge(verified)
    await gate.flush()

    assert (decision.allowed, decision.status, decision.body["error"]) == (False, 403, "key_revoked")
    assert [name for name, _ in client.calls] == ["verify", "verify"]


async def test_a_charge_after_the_verification_expired_is_decided_by_the_authority():
    clock, client = Clock(), ScriptedClient(PINNED)
    gate = _batched_gate(client, clock)
    verified = await gate.verify("Bearer ak_live.s")

    clock.now += 31
    assert (await gate.charge(verified)).allowed
    await gate.flush()

    assert [name for name, _ in client.calls] == ["verify", "consume"]


async def test_a_newer_valid_verification_of_the_same_secret_keeps_the_handle():
    clock, client = Clock(), ScriptedClient(PINNED)
    gate = _batched_gate(client, clock)
    verified = await gate.verify("Bearer ak_live.s")

    clock.now += 31
    assert (await gate.verify("Bearer ak_live.s")).key_id == "ak_live"
    assert (await gate.charge(verified)).allowed
    await gate.flush()

    assert [name for name, _ in client.calls] == ["verify", "verify", "consume_batch"]


async def test_a_handle_for_a_secret_the_gate_no_longer_holds_is_refused():
    client = SecretCheckingClient("ak_k.first", "ak_k.rotated")
    gate = TokenGate(_cfg(), client)
    verified = await gate.verify("Bearer ak_k.first")

    assert (await gate.authorize("Bearer ak_k.rotated")).allowed
    decision = await gate.charge(verified)

    assert (decision.allowed, decision.status, decision.body) == (False, 401, {"error": "invalid_api_key"})
    assert client.consumed == 1
