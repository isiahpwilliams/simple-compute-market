# Implementation Tasks

Sections are ordered by real dependency and land as five stacked pull
requests, each green on its own: Sections 2, 3, 4, and 5 are one each, and
Sections 6–8 land together. Sections 2–6 start no service and change no
existing package. Section 7 changes the development stack.

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

- [x] 1.1 Confirm `add-inference-domain-contract` is accepted and its wheel
      builds on the target branch. If its vocabulary changed in review, record
      the effect on this change in `design.md` before starting.
- [x] 1.2 Confirm by inspection that `design.md`'s "What is copied from" table
      still holds: the seven domain-package modules, the service, storefront,
      gate, and buyer exist at the named paths; the storefront's seller
      stages are still a `SettlementStageTable` keyed by mechanism and its
      configuration registry is still built from their registrations; the
      gate still charges a configured fixed amount on admission. Record drift in
      `design.md` rather than working around it.
- [x] 1.3 Record here the `dev` commit the copies are taken from. Every later
      section copies from that commit, not from whatever `dev` has become.
- [x] 1.4 Confirm Anvil development account 8 and host ports 8100, 8102, 8103,
      and 8105 are still unassigned across the Compose files and
      `dev-env/identities/README.md`; if not, choose free ones and update
      `design.md`'s tables.

Done 2026-10-17. The contract's wheel builds on this branch
(`arkhai_inference_domain-0.1.0`); its review is outstanding, so section 2
proceeds on the vocabulary as pushed and 1.1's "record the effect" clause
stays live until the review lands. Every copy source exists at its path; the
seller stages are a `SettlementStageTable` and the registry is built from
their registrations; the gate charges `amount_per_request` on admission. The
copies are taken from `dev` at `916884944`; the copy table was re-measured
there, and the reconciler's reshaping by the capacity-backing delegate is
recorded in `design.md` beside it. Anvil accounts 0 through 7 are assigned
and 8 is free; none of the four host ports appears in any Compose file,
chart, or configuration.

## 2. Domain-package semantics and the authority

- [x] 2.1 Copy into `domains/inference/src/arkhai_inference/`:
      `listings/reconciler.py`, `negotiation/policies.py`,
      `negotiation/buyer_policies.py`, `negotiation/storefront_round.py`,
      `settlement/credits_client.py`, `settlement/fulfillment.py`, and
      `settlement/issuance_evidence.py`, each under its source's file name. Apply
      the rename table. Listing reads go through `InferenceModelCard`; price
      reads go through `arkhai_inference.listings.pricing`; terms go through
      `arkhai_inference.negotiation.terms`. Record the field mapping used.
- [x] 2.2 Guards keep their semantics under inference names: round-zero shape,
      buyer counter, quota, key owned by the buyer principal, escrow shape. The
      terminal default remains the listed per-credit price, which the contract
      pins at one.
- [x] 2.3 Tests for 2.1–2.2, copied from the API-credits domain tests under
      the same rule: issuance client against a scripted authority, signed
      response verification and trust pins, fulfillment orchestration and
      rollback, evidence signing and verification, each guard's accept and
      refuse cases.
- [x] 2.4 Label pin: a test fixes one issuance request and asserts its digest
      bytes, its request and result schema strings, the evidence protocol and
      capability, and the portable fulfillment reference schema. None equals
      the API-credits value.
- [x] 2.5 Bump `arkhai-inference-domain` to 0.2.0; add the dependencies the
      copied modules import — `arkhai-kit-alkahest`, `arkhai-kit-policy`,
      and `httpx` — and relock through `scripts/uv_project.py`. Add the domain's override row to
      `docs/development/ARCHITECTURE.toml` beside the API-credits one, with the
      same owner, per `design.md`'s inherited divergence; `make
      check-architecture` passes and `make check-architecture-change
      CHANGE=compose-inference-domain-stack` reports no owned row. Extend the
      wheel-membership and installed-import tests to the new modules.
- [x] 2.6 Create `domains/inference/service/` (`arkhai-inference-service`
      0.1.0, module `inference_service`, script `inference-service`) as a copy
      of the API-credits service: configuration, container, key and system
      controllers, database, identity, signed-request middleware and route
      contracts, key models, and the key service. Environment prefix
      `INFERENCE_`. Key identifiers are issued with the `ik_` prefix. Its
      dependencies are the API-credits service's at the recorded commit —
      the site, resource-pools, and resource-pools-contracts kits, identity,
      dynaconf, FastAPI, and uvicorn — pinned as that service pins them.
- [x] 2.7 Collapse the migration history to one migration creating the
      current tables, per `design.md`'s omissions. The grant row is not
      extended.
- [x] 2.8 The authority's own copy of the issuance digest uses the `inference`
      labels. A test computes the digest for 2.4's fixed request on the
      authority side and asserts it equals the client-side bytes.
- [x] 2.9 Service tests, copied under the same rule: key issuance and top-up,
      verification, consumption and exhaustion, revocation, quota ledger
      commit and release, idempotent issuance replay, role authorization for
      `seller` and `service`, and refusal of an unsigned or wrongly signed
      request.
- [x] 2.10 `domains/inference/service/Dockerfile` building
      `arkhai:inference-service` from the repository wheelhouse through
      `uv_project.py`, and a `Makefile` with `reinit` and `test`.
- [x] 2.11 Targets `dist-inference-service`, `build-inference-service`, and
      `test-inference-service` in `domains/Makefile` and the root `Makefile`,
      joined to the aggregates; a test-matrix row.

Done 2026-10-17, from `dev` at `916884944`. The seven modules copied under
the rename table; the copies differ from their renamed sources only by the
field mapping `design.md` records beside the copy table (model-card reads in
`fulfillment.py`, the narrowed pricing call in `storefront_round.py`), proven
by a diff of each copy against its mechanically renamed source. Domain suite
188 (29 copied client, selection, and evidence tests; 15 reconciler, quota-guard,
and ownership-guard cases lifted from the API-credits storefront's unit suite
into `tests/test_guards.py`, with the backing judge written locally so the
domain package declares no resource-pools kit; the label pin in
`test_label_pin.py` fixes one request to
`inference-fulfillment.v1:2238e668…` and digest `sha256:a19cc6fa…`, and holds
every label apart from the API-credits value). The settlement-runtime kit is
not imported by the seven modules, so 2.5 declares Alkahest, policy, and
`httpx` only; the domain's override row names the inherited Alkahest import
and `check-architecture-change` reports no owned row. `arkhai-inference-service`
0.1.0 is the service copied whole; its single migration
`20261017_001_inference_schema_baseline` adopts the tables `create_all`
creates, and the owner-principal, pool-declaration, and reservation-column
history is omitted with its tests. Service suite 53, including the
authority-side pin in `tests/unit/test_issuance_label_pin.py` asserting the
client's bytes. Three copied tests wait for later sections and are recorded
here rather than stubbed: `test_credits_signed_roundtrip.py` needs the
committed `inference-*.ed25519` identities section 7 creates; the gated-app
half of the route-parity test and the three canonical-client flows that spend
through the gate's `TokensClient` need the gateway package section 4 copies;
the trust-pin test reads the storefront's TOML section 3 writes. The image
`arkhai:inference-service` is wired but was not built on this host.

## 3. Storefront

- [x] 3.1 Create `domains/inference/storefront/`
      (`arkhai-inference-storefront` 0.1.0, module `inference_storefront`,
      script `inference-storefront`) as a copy of the API-credits storefront on
      the `kit/storefront` shell: server, startup, container, lifecycle steps,
      negotiation runtime, the listings, negotiate, negotiations, settle,
      issuance-evidence, lifecycle, and system controllers, the four
      authentication middlewares, the services, and the utilities.
- [x] 3.2 Register `INFERENCE_STOREFRONT_DOMAIN` under
      `market.storefront_domains` as `inference`, declaring the capabilities
      the API-credits storefront domain declares over the `inference.v1`
      contract.
- [x] 3.3 Settlement composition with Alkahest alone: the seller stage table
      and configuration registry hold the Alkahest stage only; the payments
      seller stage, `services/payment_settlement_service.py`, the
      `[Settlement.arkhai_payments]` settings, and the lines in
      `settlement_composition.py` and `startup.py` that compose them are not
      copied; the package does not depend on `arkhai-kit-arkhai-payments`.
      Test: a configuration whose `[settlement].priority` names another
      mechanism fails at startup naming it.
- [x] 3.4 New module — publication mapping: build an `InferenceListing` from
      configuration and the quota authority, with `model_id` from
      `derive_model_id`, the endpoint set to the gateway, and backing declared
      with the backed value.
- [x] 3.5 New module — request-priced guard: refuse to publish a rate card
      with a non-zero prompt, cached-prompt, completion, or image rate, naming
      the field. Tests for each field and for a request-priced card passing.
- [x] 3.6 New module — materialization: on issuance build an
      `InferenceMaterialization` whose rate card is the stored listing's at
      acceptance. Test: republishing with a different card between acceptance
      and fulfillment does not change the materialized card.
- [x] 3.7 `[seed]` block and `storefront.inference.toml` for the development
      stack per `design.md`'s "Publication and the development listing".
- [x] 3.8 Storefront tests, copied under the same rule and extended for
      3.3–3.6: publication and reconciliation at zero and on refill,
      negotiation accept and each guard's refusal, Alkahest settlement
      verification, issuance fulfillment and its rollback, signed issuance
      evidence, administrative authentication.
- [x] 3.9 Dockerfile building `arkhai:inference-storefront`, `Makefile`,
      `dist-`, `build-`, and `test-inference-storefront` targets joined to the
      aggregates, and a test-matrix row.

Done 2026-10-17, from `dev` at `916884944`, on `feat/compose-inference-domain-stack-storefront`.
`domains/apicredits/storefront/` exported through the rename table: of the 74
copied files, 51 are identical to their renamed source and 23 differ only as
listed below; 4 are omitted and 10 are new. The renamed configuration file's
name follows it into the one docstring that cites it, and the shared
integration conftest names its temporary database after this storefront. Two renames the table implies were
applied and added to the verification rules, as section 2's copies already
applied them: the `API_CREDITS_*` constants carry `INFERENCE_`, and the prose
spellings `API-Credits`, `API-credits`, and `api-credits` read `Inference` or
`inference`, so the served OpenAPI title names this storefront; and the
`api-credit-` labels (the stored credential-reference prefix, the servicing
worker id, the OpenAPI tag) carry `inference-`, decided before this storefront
creates a database, since the prefix is persisted. The one
exception is `listing_source_check.py`'s docstring, which keeps its citation
of the API-credits specification: that is the contract the copied publication,
reconciliation, and source-recheck behaviour implements until
`extract-access-issuance-kit` lands, and the promotion record says so. Copied
comments are otherwise frozen for closeout's restatement; one already needs
it: `test_credits_trust_pins.py` recalls a comment that exists only in the
API-credits TOML.

*Omissions (3.3).* `services/payment_settlement_service.py`,
`tests/integration/test_payment_settlement.py`, and
`tests/integration/test_payment_recovery.py` are not copied.
`settlement_composition.py` loses the payments kit import, the payments stage
row, the `arkhai_payments_stage` field, `payment_service`, the
`payments_client_for_owner` parameter, and `_payments_stage`; its registry
docstring names the one registration. `settlement_stages.py` loses the
payments kit import, the two payments validators imported from the domain,
and `ArkhaiPaymentsSellerStage`. `startup.py` loses the reconciliation import
and loop; `lifecycle_steps.py` the reconciliation constant, service, step,
registration, and export; `settings.toml` the `[Settlement.arkhai_payments]`
table; `pyproject.toml` the payments kit, and the buyer dev dependency the
negotiate-CLI test needed. `tests/unit/test_settlement_mechanisms.py` proves
the table holds `alkahest.v1` alone and that resolving a `priority` naming
`arkhai.payments.v1` raises the kit's configuration error naming it, which is
the call `_build_inference_services` makes before any route is served
(unit); `tests/unit/test_startup_refusal.py` builds the services under a
foreign priority and proves they fail by name before persistence is opened.

*Substitutions (3.1, 3.4; the storefront's field mapping).*
`ListingService.publish_from_quota(service_name=, description=, openapi_url=,
base_url=)` becomes `publish_from_quota(model_card=)`; the listing payload is
`model_card.publishable_model_card(card, resource_id=, capacity_site_id=)`,
the publication resource `service` is the card's `served_model_name`, and the
creation event records `served_model_name`. `PublishFromQuotaRequest` carries
`model_card` in place of the four fields; the `publish` command takes
`--model-card PATH` (a JSON card) in place of `--service-name`,
`--description`, `--openapi-url`, `--base-url`, and `--price-per-token`, and
its docstring describes that; the escrow rate the command and the `[seed]`
block publish is `UNIT_RATE` per credit, since the contract fixes the purchase
rate at one; the seed reads `[seed.model_card]`.

*Wiring to the new modules (3.6), each one call.* `utils/migrations.py` imports
`migrate_accepted_rate_cards` and appends it to the chain as
`20261017_003_accepted_rate_cards`, so the pin's table is created, versioned,
and drift-checked with the storefront's others. `negotiation_runtime.py`
`_persist_artifacts` ends with `record_accepted_rate_card(repository,
acceptance)`, which also copies the listing binding to the thread — the
API-credits storefront never bound its threads, and the core artifact store
resolves its codec from that binding. `settlement_stages.py`: `deliver_prepared`
reads `pinned_rate_card` before issuance and, after `continue_delivery`
succeeds, calls `deliver_materialization`, which builds, records, and attaches
the materialization; `persist_delivery` adds
`public_materialization(result)` to the public result; `project_progress`
pops it from the stored public result into the response. The carrier decision
is recorded in `design.md` ("How the storefront carries it").

*New modules.* `rate_card_guard.py` (3.5), `model_card.py` (3.4: the
operator's card validated and bound to the quota resource and site, `model_id`
taken as given or derived from `owner` and `name`; the card itself names the
endpoint, which the seed points at the gateway, and backing is read from the
pool declaration by the copied binding, as the task's wording intended),
`materialization.py` (3.6: the accepted-rate-card repository on the storefront
database, the artifact-slot store that refuses a changed retry, the
public-result helpers).

*Tests (3.8).* Storefront suite 115. Unit: guard per field, model-card
binding and derivation, mechanism table and refusal, seed configuration, the
copied unit suites. Library integration (the negotiation runtime, listing
service, and reconciler against SQLite): the materialization pin surviving a
republication and refusing a changed retry; sync negotiation; publish and
reconcile; listing-source check; and, in
`tests/integration/test_materialization_delivery.py`, the coordinator flow
from verified escrow to stored credentials after a republication, asserting
the accepted card in the progress row, the status projection, and the artifact
slot (it borrows the settled deal and coordinator from the copied fulfillment
suite, which keeps them in `unit/` beside their first users). Application integration
(the composed app through the typed admin client over `ASGITransport`):
force-accept, trading pause, lifecycle routes. Copied tests adapted to the
mapping: openings below the bound use `proposal(2)` against three credits, the
bisection cases buy 300 credits at 250 so the countered midpoint stays 275,
listing fixtures are the model card in `credit_negotiation.model_card()`, rates
are one per credit, and `test_domain_runtime.py`'s foreign-model case declares
only `kind` and admits the card's other fields as extras. The three cases the
source drove through the payments option are rewritten in
`test_sync_negotiation.py` against the listing's Alkahest option: the
opening-selection-switch and withdrawn-option revalidation rules, which the
copied adapter raises, are proven here, and an Alkahest acceptance places no
quota hold.
`test_concept_modules.py` keeps only the storefront's reference-hook test; the
rest exercised domain modules the domain suite already covers, or API-credits
per-token pricing the contract replaces. `test_credits_negotiate_cli.py`
drives `market inference negotiate` and waits for section 5. The domain's
`test_credits_trust_pins.py` is copied now that the TOML exists; its third
case skips until section 7 commits `inference-service.ed25519`.

*Seed (3.7).* `storefront.inference.toml`: Anvil account 8
(`0x23618e81…b21e8f`), one credit per request, `dev://arkhai/stub-instruct`,
`model_id` derived from owner `arkhai` and name `stub-instruct`, endpoint
`http://inference-gateway:8105/v1`, quota 100000. The file is this stack's
configuration, written for it rather than copied, so its comments are its own.
It sets no `hold_ttl_seconds`: only the omitted payments stage placed an
acceptance-time quota hold, so inference reserves quota at fulfillment and the
setting has no reader here.
The registry and authority
pins are the public halves of seeds derived as the identities README
prescribes, from `arkhai-development-inference-registry-v1`
(`QpkX0mKY…`) and `arkhai-development-inference-service-v1` (`nS5GC-Q7…`);
neither begins with `-`. For section 7: generate `inference-registry.ed25519`
and `inference-service.ed25519` from those labels, mount the administrative
key at `/run/secrets/arkhai/inference-admin-key`, and for section 4: the
gateway listens on 8105 and serves under `/v1`.

*Build (3.9).* `Dockerfile` and `Makefile` identical to the source after
rename; `dist-/build-/test-inference-storefront` in both Makefiles, the
inference Makefile's `test-storefront`, the four-image `build` line gains the
storefront, and a `tests.yml` row. `arkhai:inference-storefront` was not
built on this host. End-to-end markers: none exercise this section yet;
section 7 adds `e2e_inference_deal`.

*Owed to later work.* Section 5: the storefront client's status model admits
the `materialization` field only through its catch-all `extra` mapping, so the
buyer's typed client gains a named field before the plugin reads it.
`extract-access-issuance-kit`: `tests/unit/test_settlement_fulfillment.py`
runs a real SQLite coordinator from `unit/`, and the testing guide asks that
such a suite move to `integration/` when next touched; it stays beside its
source until the extraction so the copy comparison has one less difference to
explain.

*Checks.* `make check-packaging` (which runs `check-architecture`),
`check-comment-hygiene`, `check-doc-citations`, `check-architecture-change`,
`check-change-index`, `check-tasks`, and `openspec validate --strict` pass.
`make -k test` runs every project; every suite this section touches is green,
and the four failures are in projects it does not touch and are this macOS
host's, since upstream's `tests.yml` run at `916884944` passes them:
`provisioning/compute/service`'s dotenv-layer test, which fails identically
under a minimal environment; `provisioning/compute/iac`'s three relay-teardown
tests; the VM storefront's two `test_alkahest.py` toolchain tests; and
`scripts/tests/test_validate_slice.py`, which needs a `make` with `--eval`.
The fresh-context review's accepted findings were fixed before the commit; its
duplicate-registry and typing remarks were declined: the materialization store
builds the one-registration registry from the domain contract it is handed,
and threading the composed app's registry into the stage would add wiring
lines to copies, while `Any`-typed repository and acceptance parameters follow
the copied modules' own convention.

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
      when `model` is not the configured served model. Test: a refused request
      makes no authority call.
- [ ] 4.4 `GET /v1/models` listing only the configured model and `GET /health`,
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
      `test-` targets joined to the aggregates, and test-matrix rows.

## 5. Buyer plugin

- [ ] 5.1 Create `domains/inference/buyer/` (`arkhai-inference-buyer` 0.1.0,
      module `arkhai_inference_buyer`) as a copy of the API-credits buyer
      plugin, registered under `market.buyer_domains` as `inference` with the
      command group `market inference` and the `inference` schema identity.
- [ ] 5.2 Alkahest alone: the buyer's `payments.py`, its payments stage, and
      the lines in `buy_cli.py` and `settlement_composition.py` that compose
      them are not copied; the package does not depend on
      `arkhai-kit-arkhai-payments`.
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
      targets joined to the aggregates, a test-matrix row, and the plugin
      added to the end-to-end image's dependencies.

## 6. Composition and distribution checks

- [ ] 6.1 Distribution tests for the inference projects, following the
      API-credits pattern: each role wheel carries its own modules and none of
      the domain wheel's; each requires the domain wheel and its versioned core
      role package; no project declares an internal editable source; no role
      wheel requires `arkhai-kit-arkhai-payments`.
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
      independent named volumes; the `vllm` profile replacing the stub and
      selecting a storefront configuration that lists the model it serves.
- [ ] 7.3 `compose.inference.yml` standalone wrapper; the domain file included
      from the root `docker-compose.yml`; registry authority, storefront
      identity, and wallet bindings in `compose.inference-local.yml`, and
      `compose.inference-lane.yml` only if the scenario needs a second
      registry; a one-shot buyer service as the API-credits overlay has.
- [ ] 7.4 `e2e-inference-dev-env` at the root prints the six inference
      variables, the identities README counts them, and the e2e-tests
      `Makefile` gains `test-e2e-inference`, `e2e-inference-logs`, and
      `e2e-inference-down` on the API-credits lane's pattern, run as an
      `e2e-inference` job in `.github/workflows/e2e.yml`.
- [ ] 7.5 Static stack tests beside the API-credits ones: no committed
      administrative credential, independent volumes, images installing only
      their staged wheels, the registry selecting the `inference`
      specification, and the gateway's configured charge and served model
      equal to the seeded listing's `request_credits` and `served_model_name`.
- [ ] 7.6 End-to-end settings for the inference registry and gateway URLs; the
      `e2e_inference_deal` marker; the marker added to the VM lane's module
      expression.
- [ ] 7.7 `e2e_inference_deal` through the shared domain-neutral helpers, with
      the eight steps in `design.md`'s "The end-to-end scenario".
- [ ] 7.8 The four images join `make build`.

## 8. Closeout

- [ ] 8.1 **Comment hygiene.** Confirm `make check-comment-hygiene` passes and
      that the pre-closeout review's triage restated every copied comment that
      described API credits or the copy itself as current inference behaviour.
- [ ] 8.2 **Import placement.** Confirm that, before the pre-closeout review,
      function-level imports added or carried by the copies were moved to
      module level except for a verified circular import or a documented lazy
      load.
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
- [ ] 8.7 **Packaging.** `make check-packaging`, which includes the
      architecture check over the five new projects, then
      `make check-architecture-change CHANGE=compose-inference-domain-stack`:
      every exception or override row this change owns is deleted with its
      cause before archival.
- [ ] 8.8 **End-to-end pipeline.** Record the lane run, its result, and that
      `e2e_inference_deal` ran in it. If the pipeline cannot run for a reason
      unrelated to this change, record the blocker and the change that owns it,
      and treat the scenario as unrun.
- [ ] 8.9 **Promotion.** Write the permanent documents the record below names
      and complete the design promotion record, after code review.
- [ ] 8.10 **Documentation citations.** After promotion,
      `make check-doc-citations CHANGE=compose-inference-domain-stack` and
      `openspec validate compose-inference-domain-stack --strict`.
- [ ] 8.11 **Archival.** `openspec archive compose-inference-domain-stack -y`
      once every part above is done; update the campaign row to `archived`
      and the dependency graph in `openspec/changes/README.md`.

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
| Quota-backed publication, reconciliation, and source recheck as the inference storefront copies them | normative in `openspec/specs/api-credits/spec.md` until `extract-access-issuance-kit` moves the shared behaviour; the copied docstrings cite it |
| Roadmap and campaign index currency | `docs/development/ROADMAP.md` Goal 8; `openspec/changes/README.md` |
