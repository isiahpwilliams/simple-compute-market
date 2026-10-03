# Implementation Tasks

Sections are ordered by real dependency. Each of Sections 2–7 is one stacked
pull request, green on its own; `design.md`'s "Landing in reviewable slices"
gives the grouping. Sections 2–6 start no service and change no existing
package. Section 7 changes the development stack.

**Standing rule for every copied module.** `design.md`'s "Copies are frozen, and
the permitted differences are enumerated" is the whole of what a copy may
change: the listed renames, substitutions, and omissions, with new behaviour in
new modules. Each section's pull request shows the copied modules' diff against
their sources after renames.

**Decision gates.** None. `design.md` carries four decisions that amend the
proposal — Alkahest-only settlement, the materialization-side rate-card pin,
request-priced publication, and the stub model server — and the proposal is
amended to match.

## 1. Baseline and copy record

- [ ] 1.1 Confirm `add-inference-domain-contract` is accepted and its wheel
      builds on the target branch. If its vocabulary changed in review, record
      the effect on this change in `design.md` before starting.
- [ ] 1.2 Confirm by inspection that `design.md`'s "What is copied from" table
      still holds: the seven domain-package modules, the service, storefront,
      gate, and buyer exist at the named paths; the storefront's settlement
      registry is still built from mechanism registrations; the gate still
      charges a configured fixed amount on admission. Record drift in
      `design.md` rather than working around it.
- [ ] 1.3 Record here the `dev` commit the copies are taken from. Every later
      section copies from that commit, not from whatever `dev` has become.
- [ ] 1.4 Confirm Anvil development account 8 and host ports 8100, 8102, 8103,
      and 8105 are still unassigned across the Compose files and
      `dev-env/identities/README.md`; if not, choose free ones and update
      `design.md`'s tables.

## 2. Domain-package semantics and the authority

- [ ] 2.1 Copy into `domains/inference/src/arkhai_inference/`:
      `listings/reconciler.py`, `negotiation/policies.py`,
      `negotiation/buyer_policies.py`, `negotiation/storefront_round.py`,
      `settlement/credits_client.py` as `settlement/issuance_client.py`,
      `settlement/fulfillment.py`, and `settlement/issuance_evidence.py`. Apply
      the rename table. Listing reads go through `InferenceModelCard`; price
      reads go through `arkhai_inference.listings.pricing`; terms go through
      `arkhai_inference.negotiation.terms`. Record the field mapping used.
- [ ] 2.2 Guards keep their semantics under inference names: round-zero shape,
      buyer counter, quota, key owned by the buyer principal, escrow shape. The
      terminal default remains the listed per-credit price, which the contract
      pins at one.
- [ ] 2.3 Tests for 2.1–2.2, copied from the API-credits domain tests under
      the same rule: issuance client against a scripted authority, signed
      response verification and trust pins, fulfillment orchestration and
      rollback, evidence signing and verification, each guard's accept and
      refuse cases.
- [ ] 2.4 Label pin: a test fixes one issuance request and asserts its digest
      bytes, its request and result schema strings, the evidence protocol and
      capability, and the portable fulfillment reference schema. None equals
      the API-credits value.
- [ ] 2.5 Bump `arkhai-inference-domain` to 0.2.0; add the kit dependencies the
      copied modules import; relock through `scripts/uv_project.py`. Extend the
      wheel-membership and installed-import tests to the new modules.
- [ ] 2.6 Create `domains/inference/service/` (`arkhai-inference-service`
      0.1.0, module `inference_service`, script `inference-service`) as a copy
      of the API-credits service: configuration, container, key and system
      controllers, database, identity, signed-request middleware and route
      contracts, key models, and the key service. Environment prefix
      `INFERENCE_`. Key identifiers are issued with the `ik_` prefix.
- [ ] 2.7 Omit the legacy issuance path and collapse the migration history to
      one migration creating the current tables, per `design.md`'s omissions.
      The grant row is not extended.
- [ ] 2.8 The authority's own copy of the issuance digest uses the `inference`
      labels. A test computes the digest for 2.4's fixed request on the
      authority side and asserts it equals the client-side bytes.
- [ ] 2.9 Service tests, copied under the same rule: key issuance and top-up,
      verification, consumption and exhaustion, revocation, quota ledger
      commit and release, idempotent issuance replay, role authorization for
      `seller` and `service`, and refusal of an unsigned or wrongly signed
      request.
- [ ] 2.10 `domains/inference/service/Dockerfile` building
      `arkhai:inference-service` from the repository wheelhouse through
      `uv_project.py`, and a `Makefile` with `reinit` and `test`.
- [ ] 2.11 Targets `dist-inference-service`, `build-inference-service`, and
      `test-inference-service` in `domains/Makefile` and the root `Makefile`,
      joined to the aggregates; a test-matrix row with no hosted-release
      requirement.

## 3. Storefront

- [ ] 3.1 Create `domains/inference/storefront/`
      (`arkhai-inference-storefront` 0.1.0, module `inference_storefront`,
      script `inference-storefront`) as a copy of the API-credits storefront on
      the `kit/storefront` shell: server, startup, container, lifecycle steps,
      negotiation runtime, the listings, negotiate, negotiations, settle,
      issuance-evidence, lifecycle, and system controllers, the four
      authentication middlewares, the services, and the utilities.
- [ ] 3.2 Register `INFERENCE_STOREFRONT_DOMAIN` under
      `market.storefront_domains` as `inference`, declaring the capabilities
      the API-credits storefront domain declares over the `inference.v1`
      contract.
- [ ] 3.3 Settlement composition with Alkahest alone: the configuration
      registry holds the Alkahest registration only; the hosted agreement,
      fulfillment, projection, cleanup, routes, controller, and settlement
      models are not copied; the package does not depend on
      `arkhai-kit-hosted-settlement`. Test: a configuration whose
      `[settlement].priority` names another mechanism fails at startup naming
      it.
- [ ] 3.4 New module — publication mapping: build an `InferenceListing` from
      configuration and the quota authority, with `model_id` from
      `derive_model_id`, the endpoint set to the gateway, and backing declared
      with the backed value.
- [ ] 3.5 New module — request-priced guard: refuse to publish a rate card
      with a non-zero prompt, cached-prompt, completion, or image rate, naming
      the field. Tests for each field and for a request-priced card passing.
- [ ] 3.6 New module — materialization: on issuance build an
      `InferenceMaterialization` whose rate card is the stored listing's at
      acceptance. Test: republishing with a different card between acceptance
      and fulfillment does not change the materialized card.
- [ ] 3.7 `[seed]` block and `storefront.inference.toml` for the development
      stack per `design.md`'s "Publication and the development listing".
- [ ] 3.8 Storefront tests, copied under the same rule and extended for
      3.3–3.6: publication and reconciliation at zero and on refill,
      negotiation accept and each guard's refusal, Alkahest settlement
      verification, issuance fulfillment and its rollback, signed issuance
      evidence, administrative authentication.
- [ ] 3.9 Dockerfile building `arkhai:inference-storefront`, `Makefile`,
      `dist-`, `build-`, and `test-inference-storefront` targets joined to the
      aggregates, and a test-matrix row with no hosted-release requirement.

## 4. Gateway and model stub

- [ ] 4.1 Create `domains/inference/gateway/` (`arkhai-inference-gateway`
      0.1.0, module `inference_gateway`, script `inference-gateway`). Copy the
      Python bearer gate — configuration, authority client, signing, gate, and
      ASGI middleware — into `inference_gateway/gate/` with the
      `INFERENCE_GATEWAY_` prefix. Copy its tests and the conformance session
      runner under the same rule.
- [ ] 4.2 New module — proxy: `POST /v1/chat/completions` and
      `POST /v1/completions` forwarded to the configured model server; the
      buyer's `Authorization` removed and an optional mounted upstream
      credential sent in its place; hop-by-hop headers removed both ways;
      server-sent events forwarded unbuffered; model-server errors passed
      through; `502` when unreachable and `504` on timeout.
- [ ] 4.3 New module — model check, outside the gate: bounded body read, `413`
      over the limit, `400` when not a JSON object, `404` `model_not_found`
      when `model` is not a configured served model. Test: a refused request
      makes no authority call.
- [ ] 4.4 `GET /v1/models` listing only configured models and `GET /health`,
      both ungated; every other path `404`.
- [ ] 4.5 Gateway tests against a scripted authority and a scripted model
      server: admitted and charged; `401` missing and unknown key; `403`
      revoked; `402` with the purchase pointer at exhaustion; the credential is
      never forwarded; a streamed response arrives chunk by chunk before the
      upstream closes; upstream `500` is passed through.
- [ ] 4.6 Create `domains/inference/model-stub/`
      (`arkhai-inference-model-stub` 0.1.0, script `inference-model-stub`): a
      deterministic OpenAI-compatible server for chat completions and
      completions that reports `usage` and streams server-sent events with a
      final usage chunk when `stream_options.include_usage` is set. Tests pin
      its response bodies.
- [ ] 4.7 Dockerfiles building `arkhai:inference-gateway` and
      `arkhai:inference-model-stub`, `Makefile`s, `dist-`, `build-`, and
      `test-` targets joined to the aggregates, and test-matrix rows with no
      hosted-release requirement.

## 5. Buyer plugin

- [ ] 5.1 Create `domains/inference/buyer/` (`arkhai-inference-buyer` 0.1.0,
      module `arkhai_inference_buyer`) as a copy of the API-credits buyer
      plugin, registered under `market.buyer_domains` as `inference` with the
      command group `market inference` and the `inference` schema identity.
- [ ] 5.2 Alkahest alone: hosted authorization and every hosted branch in the
      buy, settle, and settlement-composition modules are not copied; the
      package does not depend on `arkhai-kit-hosted-settlement`.
- [ ] 5.3 New module — listing filters for model, model family, quantization,
      modality, supported parameter, provenance, minimum context length, and
      the two rate bounds, compiled from the served filter specification.
      Test: a rate bound without a settlement asset is refused before any
      request is sent, with the rule read from a served specification fixture
      and not from code.
- [ ] 5.4 Listing rendering shows the model card: model, provenance,
      quantization, context length, the rate card, and the endpoint. A
      completed purchase prints the key, the gateway base URL, and the served
      model name.
- [ ] 5.5 Buyer tests, copied under the same rule and extended for 5.3–5.4:
      plugin export and command surface, schema-filtered discovery, negotiate
      and buy for a new key and for an existing key, settlement status.
- [ ] 5.6 `Makefile`, `dist-inference-buyer` and `test-inference-buyer`
      targets joined to the aggregates, a test-matrix row with no
      hosted-release requirement, and the plugin added to the end-to-end image's
      dependencies.

## 6. Composition and distribution checks

- [ ] 6.1 Distribution tests for the inference projects, following the
      API-credits pattern: each role wheel carries its own modules and none of
      the domain wheel's; each requires the domain wheel and its versioned core
      role package; no project declares an internal editable source; no role
      wheel requires `arkhai-kit-hosted-settlement`.
- [ ] 6.2 Installed-environment test: the storefront and buyer entry points
      load from built wheels and the domain registers once under each group.
- [ ] 6.3 Boundary test: no inference module imports `arkhai_apicredits`,
      `apicredits_storefront`, `apicredits_service`, `apicredits_middleware`, or
      `arkhai_apicredits_buyer`, including under `TYPE_CHECKING`.

## 7. Stack, identities, and the end-to-end scenario

- [ ] 7.1 Generate the development identities in `design.md`'s table under
      `dev-env/identities/` and document each in that directory's README as a
      well-known development value, with its account assignment and where it is
      pinned.
- [ ] 7.2 `domains/inference/compose.yml` with the five services, their
      health checks, memory limits, role-scoped credential mounts guarded by
      `${VAR:?…}`, pinned trusted principals and expected authorities, and
      independent named volumes; the `vllm` profile replacing the stub.
- [ ] 7.3 `compose.inference.yml` standalone wrapper; the domain file included
      from the root `docker-compose.yml`; registry authority, storefront
      identity, and wallet bindings in `compose.local-identities.yml`; a
      one-shot buyer service as the API-credits wrapper has.
- [ ] 7.4 `e2e-dev-identities-env` prints the six inference variables; the
      comment above it and the identities README count them.
- [ ] 7.5 Static stack tests beside the API-credits ones: no committed
      administrative credential, independent volumes, images installing only
      their staged wheels, and the registry selecting the `inference`
      specification.
- [ ] 7.6 End-to-end settings for the inference registry and gateway URLs; the
      `e2e_inference_deal` marker; the marker added to the VM lane's module
      expression.
- [ ] 7.7 `e2e_inference_deal` through the shared domain-neutral helpers, with
      the eight steps in `design.md`'s "The end-to-end scenario".
- [ ] 7.8 The four images join `make build`.

## 8. Closeout

- [ ] 8.1 **Comment hygiene.** `make check-comment-hygiene`; then read every
      copied module for comments that describe API credits or the copy itself
      and restate them as current inference behaviour.
- [ ] 8.2 **Import placement.** Review function-level imports added or carried
      by the copies; keep a local import only for a verified circular import or
      a documented lazy load.
- [ ] 8.3 **Documentation compliance.** Re-check this change's accepted
      decisions against `openspec/README.md`'s placement rules.
- [ ] 8.4 **Narrative compression.** Reduce completed-task notes to final
      behaviour, material validation evidence, deferred work, and permanent
      destinations.
- [ ] 8.5 **Roadmap currency.** Update Goal 8's current state and its
      gap-to-change table in `docs/development/ROADMAP.md`: the roles, stack,
      and deal path exist; request-priced publication and admission-time
      charging are the remaining gaps `meter-inference-usage` owns.
- [ ] 8.6 **Campaign index currency.** Update this change's row in
      `openspec/changes/README.md`, and `extract-access-issuance-kit`'s, whose
      dependency on a green deal is then met.
- [ ] 8.7 **Documentation citations.**
      `make check-doc-citations CHANGE=compose-inference-domain-stack`.
- [ ] 8.8 **Packaging.** `make check-packaging`.
- [ ] 8.9 **End-to-end pipeline.** Record the lane run, its result, and that
      `e2e_inference_deal` ran in it. If the pipeline cannot run for a reason
      unrelated to this change, record the blocker and the change that owns it,
      and treat the scenario as unrun.
- [ ] 8.10 **Promotion.** Complete the design promotion record below after
      code review.

## Design promotion record

| Accepted decision | Permanent location |
|---|---|
| Inference roles: storefront, authority, gateway, buyer plugin, and what each owns | the `inference` capability's `spec.md`; the `inference` capability's `architecture.md` |
| Alkahest is the only inference settlement mechanism, enforced by registration | the `inference` capability's `spec.md`; the `inference` capability's `architecture.md` |
| The gateway's surface: gated routes, model check before charge, credential not forwarded, unbuffered streaming | the `inference` capability's `spec.md` |
| Rate card pinned in the materialization at acceptance | the `inference` capability's `spec.md` |
| Only request-priced rate cards are publishable until metered consumption exists | the `inference` capability's `spec.md`; the `inference` capability's `architecture.md` |
| Inference keys, grants, and state are separate from every other domain's | the `inference` capability's `spec.md` |
| Shipped domains include inference | `openspec/specs/market-composition/spec.md` |
| Local inference stack: third registry schema, role-scoped development identities, independent volumes | `openspec/specs/deployment-state/spec.md`; `docs/development/ARCHITECTURE.md` runtime service map and local topology |
| Inference end-to-end deal path through shared helpers against a deterministic model server | `openspec/specs/test-compatibility/spec.md`; `docs/development/TESTING.md` |
| Copy-then-extract sequencing and the frozen-copy rule | not promoted; change history, superseded when `extract-access-issuance-kit` lands |
| Roadmap and campaign index currency | `docs/development/ROADMAP.md` Goal 8; `openspec/changes/README.md` |
