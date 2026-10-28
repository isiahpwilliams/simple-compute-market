## Why

`add-inference-domain-contract` defines what an inference listing, purchase,
and usage record mean, and `compose-api-family-kit` owns the machinery any
API-selling domain needs to sell access against them. Nothing runs inference.
This change composes the smallest set of roles that can complete one inference
deal on the local development stack and proves that deal end to end, so the
vocabulary is exercised by real buyer and seller boundaries.

The roles are thin composition roots over the family kit. Inference contributes
what the kit cannot know — a model-card listing built from the quota authority,
a guard refusing rate cards the stack cannot yet charge, a materialization that
pins the listing's rate card at acceptance, and the gateway's model check — and
wires the kit's issuance, key authority, gate client, and credits ledger around
them. An earlier version of this change copied the API-credits roles instead and
was withdrawn once the copy measured what inference adds: fewer than 300 lines
against about 12,500 copied. Those three modules, the development seed, and the
startup refusal of a foreign settlement mechanism carry over from it.

Consumption in this change is a **flat charge per request**, using the kit's
gate and authority as API credits ships them. That is not the inference
billing model; it is the smallest thing that proves the market plumbing —
discover, negotiate, settle, issue, call the model, exhaust, top up — is
correct. `meter-inference-usage` replaces the charge model on a stack that
already works. So that no listing advertises a price the stack does not charge,
only request-priced rate cards are publishable until then.

## What Changes

- **Storefront.** An `inference-storefront` executable on the `kit/storefront`
  shell, registered under `market.storefront_domains`, composing the family
  kit's issuance fulfillment, reconciler, and settlement composition with
  Alkahest as its only settlement mechanism, and contributing publication of
  model-card listings from the quota authority, the kit's seller round hook,
  the request-priced guard, and the delivery's public result, which carries the
  contract's `InferenceMaterialization` built from the accepted listing the kit
  pins at acceptance.
- **Authority.** An `arkhai:inference-service` image composing the kit's key
  authority and credits ledger under the issuance digest label `inference`,
  with its own database and key namespace, as a service root of its own over
  the kit's `authority` library: the family keeps each domain's root separate,
  since two domains never share a process (the `api-family` capability's
  `architecture.md`, "Service roots and the capacity profile").
- **Gateway.** A family library, `arkhai-api-gateway` under `domains/api`: an
  OpenAI-compatible reverse proxy in front of a model server that checks the
  requested model before charging, authorizes and charges through the kit's
  bearer gate inside the route, never forwards the buyer's credential, streams
  upstream responses unbuffered, serves `/v1/models` listing the one configured
  model, and carries a per-request verification seam for a later attestation
  proof. Inference composes it as the `arkhai:inference-gateway` image from a
  `gateway-service` root that reads and validates the listing the gateway
  fronts, projects it to the family's offering, and supplies the upstream and
  the gate's `service`-role signing credential; a request is charged the
  `request_credits` its key was issued under, which issuance pins on the key
  and verification returns.
- **Buyer.** An `arkhai-inference-buyer` plugin under `market.buyer_domains`
  composing the kit's purchase flow and contributing `market inference listing
  list|show`, `buy`, `negotiate`, `settle`, and `settlement status`, the
  `inference` schema identity, model-card discovery filters, and model-card
  rendering, with Alkahest settlement only.
- **Stack.** `domains/inference/compose.yml` (inference registry selecting the
  packaged filter specification by path, authority, gateway, storefront, and a
  model server) with the per-domain `compose.inference.yml`,
  `compose.inference-local.yml`, and `compose.inference-lane.yml` files;
  development identities under `dev-env/identities/` and the
  `e2e-inference-dev-env` variables. The model server is a deterministic
  OpenAI-compatible stub built under `e2e-tests/`, so the scenario runs
  without a GPU or an external model download and asserts exact responses; a
  Compose profile swaps in the CPU vLLM image with a small instruct model.
- **Scenario.** `e2e_inference_deal`: discover by model, negotiate a new key,
  settle on the development chain, call `/v1/chat/completions`, be refused an
  unlisted model without charge, consume to `402`, top up the existing key,
  call again, and stream a response — through the shared domain-neutral
  helpers, not a copied VM or API-credits scenario.
- **Build.** `dist-inference-{storefront,buyer,service,gateway,model-stub}`,
  `build-inference-*`, and `test-inference-*` targets; the images join
  `make build`. No inference project needs a separately released dependency.

## Capabilities

### Modified Capabilities

- `inference`: the storefront, authority, gateway, and buyer roles exist and
  complete one deal; flat per-request consumption is the version-1 posture
  until metering lands.
- `api-family`: the kit's contribution surface gains its second consumer; the
  family gains a gateway library in front of OpenAI-style model servers; the
  issuance subject may carry accepted terms, which the authority pins on the
  key and `verify` returns; the authority scopes a key to its first grant; the
  gate gains a separable verify step.
- `market-composition`: the "shipped domains are loaded" scenario gains the
  inference plugin.
- `deployment-state`: a third registry schema is deployable locally; the
  development identity set and Compose wiring gain the inference roles.
- `test-compatibility`: the per-domain end-to-end deal path exists for
  inference.

## Non-Goals

- No domain-local implementation of anything the family kit owns.
- No admission holds, usage capture, or per-token charging.
- No fiat (`arkhai.payments.v1`) option, no Helm alias, no Arkhai-hosted
  registry, no webapp.
- No per-token rate card on a published listing.
- No seller installer or packaging beyond the Compose stack.
- No TypeScript or Rust gate.

## Dependencies and Related Changes

- **Depends on** `add-inference-domain-contract` and
  `repair-storefront-alkahest-configuration` accepted. `compose-api-family-kit`
  is closed out and archived; its index row advances at archive cleanup, and
  its kit is what this change composes.
- **Consumes** `sign-multi-language-credits-middleware`'s Python signing path
  as it stands; does not wait on its TypeScript and Rust work.
- **Enables** `meter-inference-usage` by supplying the stack it changes.
- `repair-storefront-alkahest-configuration` owns the development stack's
  Alkahest readiness; this change's scenario needs it green, so it gates
  implementation.

## Impact

- New: `domains/api/gateway/`,
  `domains/inference/{storefront,buyer,service,gateway-service}/`, the model
  stub under `e2e-tests/`,
  `domains/inference/compose.yml`, the per-domain Compose files, development
  identities, the `e2e-inference-dev-env` target, the e2e lane targets, the
  e2e scenario and marker.
- Touched: root `docker-compose.yml`, `domains/Makefile`, root `Makefile`,
  `e2e-tests/Makefile`, `.github/workflows/e2e.yml`,
  `e2e-tests/pyproject.toml` markers.
- Wire: none beyond the new domain. Database: one new service database, not
  shared. Deployment: new images and one more registry instance in the
  development stack.

## Permanent documentation impact

- [x] `docs/development/ARCHITECTURE.md` — runtime service map and local
      deployment topology gain the inference roles and third registry schema.
- [x] Existing subsystem specification — `market-composition`,
      `deployment-state`, `test-compatibility` scenarios; `api-family`'s
      second consumer and its gateway library.
- [x] New subsystem specification — `inference` gains the role-composition and
      end-to-end requirements.

### Knowledge to promote

| Decision | Permanent destination |
|---|---|
| The issuance projection names the served model and delivers the gateway URL (D1) | the `inference` capability's `spec.md`; the `api-family` capability's `architecture.md` contribution table, inference column |
| The gateway is a family library composed by a domain executable (D2) | the `api-family` capability's `spec.md` and `architecture.md`; `docs/development/ARCHITECTURE.md` runtime service map |
| The public result carries the contract's materialization; the kit's accepted-listing artifact is the pinned card (D3) | the `inference` capability's `spec.md` and `architecture.md` |
| Retry charges and the metering seam (D4) | the `inference` capability's `architecture.md` — "Current limits" |
| The stub model server is a test image; the `vllm` profile (D5) | `docs/development/DEPLOYMENT_AND_CONFIG.md`; the `deployment-state` capability's `spec.md` |
| Contribution values, publish request, guard, Alkahest-only refusal (D6–D9, D12) | the `inference` capability's `spec.md` |
| Compose files, identities, lane (D10, D11) | the `deployment-state` and `test-compatibility` capabilities' `spec.md`; `dev-env/identities/README.md` |
| Verification seams and the measurable image (D16) | the `inference` capability's `architecture.md`; the `api-family` capability's `architecture.md` |
| The three-party constraint on settlement composition (D17) | the `inference` capability's `architecture.md` |
| A key is scoped to its first grant's service, resource, and accepted terms (F4, review 02 F1) | the `api-family` capability's `spec.md` |
| The issuance subject carries the accepted terms digest and request charge; the gateway charges the key's verified charge (F1) | the `inference` capability's `spec.md`; the `api-family` capability's `spec.md` and `architecture.md` contribution table |
| The family gateway consumes a domain-neutral offering the domain executable projects (review 02 F3) | the `api-family` capability's `spec.md` and `architecture.md` |
| The proof hook binds to the accepted attestation through the terms digest (review 02 F2) | the `inference` capability's `architecture.md` |
| Verification precedes the charge; the gate's separable verify step (F3) | the `api-family` capability's `spec.md` and `architecture.md` |
| A top-up is admitted after the gate's verification TTL (F2) | the `inference` capability's `spec.md`; `architecture.md` — "Current limits" |

## Status

Returned to design on 2026-10-19; the copy-based `design.md` and `tasks.md`
were withdrawn with the copied implementation. Redesigned on 2026-10-28
against the `api` family kit, archived on 2026-10-26, and the contract as
implemented; design reviews 01 and 02 were triaged on 2026-10-28 and their
gaps are decided in `design.md`, which awaits a third design review.
