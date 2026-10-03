## Why

`add-inference-domain-contract` defines what an inference listing, purchase,
and usage record mean. Nothing runs it. This change composes the smallest set
of roles that can complete one inference deal on the local development stack
and proves that deal end to end, so the vocabulary is exercised by real buyer
and seller boundaries before anything is generalized.

It deliberately **copies** the API-credits issuance client, fulfillment
orchestration, evidence projection, and role compositions into the inference
domain rather than extracting them first. `add-inference-domain-contract`'s design records why:
the shared boundary is not knowable from one consumer, and the extraction is
delicate — the schema strings are inside SHA-256 digests and the authority
keeps a mirror of the digest function — so it is done once two working
consumers exist. This change is the second consumer.

Consumption in this change is a **flat charge per request**, using the gate
and authority exactly as API credits ships them. That is not the inference
billing model; it is the smallest thing that proves the market plumbing — discover,
negotiate, settle, issue, call the model, exhaust, top up — is correct.
`meter-inference-usage` replaces the charge model on a stack that already works.
So that no listing advertises a price the stack does not charge, only
request-priced rate cards are publishable until then.

## What Changes

- **Storefront.** An `inference-storefront` executable on the `kit/storefront`
  shell, registered under `market.storefront_domains`, mirroring the API-credits
  storefront's composition: publication of model-card listings from the quota
  authority, seller round hook over per-credit pricing, Alkahest settlement
  verification, issuance fulfillment, and the reconciler. Copied from
  `domains/apicredits/storefront/` with the domain contract and codecs swapped
  and the hosted settlement mechanism left out: Alkahest is the only mechanism
  it registers. It delivers a materialization pinning the listing's rate card,
  and refuses to publish a rate card with token or image rates.
- **Authority.** An `arkhai:inference-service` image from a copy of the
  API-credits service composition — keys, grants, consumption, quota ledger,
  signed authentication — with the issuance digest label `inference`. Its
  tables are unchanged from the source; the pinned rate card travels in the
  storefront's materialization, and storing it where consumption reads it is
  `meter-inference-usage`'s. Separate database and separate key namespace from
  any API-credits deployment.
- **Gateway.** An `arkhai:inference-gateway` image: an OpenAI-compatible reverse
  proxy in front of a model server, gated by a copy of the Python bearer gate
  signing as the `service` role, charging the listing's per-request credits on
  admission, with `/v1/models` filtered to the models the seller lists. A
  request naming an unlisted model is refused before any charge, and the
  buyer's credential is never forwarded. Streaming responses are passed through
  unbuffered even though nothing yet reads their usage.
- **Buyer.** An `arkhai-inference-buyer` plugin under `market.buyer_domains`
  contributing `market inference listing list|show`, `buy`, `negotiate`,
  `settle`, and `settlement status`, declaring the `inference` schema identity,
  with model-card discovery filters and Alkahest settlement only.
- **Stack.** `domains/inference/compose.yml` (inference registry with the
  filter specification mounted, authority, gateway, storefront, and a model
  server) and a root `compose.inference.yml` wrapper; inclusion in the root
  `docker-compose.yml`; development identities under `dev-env/identities/`
  (`inference-registry.ed25519`, `inference.identity.env`,
  `inference.wallet.env`, gated-app and service principals) with their
  `compose.local-identities.yml` bindings and `e2e-dev-identities-env`
  variables. The model server is a deterministic OpenAI-compatible stub built
  from this repository, so the scenario runs without a GPU or an external model
  download and asserts exact responses; a Compose profile swaps in the CPU vLLM
  image with a small instruct model.
- **Scenario.** `e2e_inference_deal`: discover by model, negotiate a new key,
  settle on the development chain, call `/v1/chat/completions`, be refused an
  unlisted model without charge, consume to `402`, top up the existing key,
  call again, and stream a response — through the shared
  domain-neutral helpers, not a copied VM or API-credits scenario.
- **Build.** `dist-inference-{storefront,buyer,service,gateway,model-stub}`,
  `build-inference-*`, and `test-inference-*` targets; the four images join
  `make build`. No inference project needs a separately released dependency.

## Capabilities

### Modified Capabilities

- `inference`: the storefront, authority, gateway, and buyer roles exist and
  complete one deal; flat per-request consumption is the version-1 posture
  until metering lands.
- `market-composition`: the "shipped domains are loaded" scenario gains the
  inference plugin.
- `deployment-state`: a third registry schema is deployable locally; the
  development identity set and Compose wiring gain the inference roles.
- `test-compatibility`: the per-domain end-to-end deal path exists for
  inference.

## Non-Goals

- No extraction from API credits; both copies coexist until
  `extract-access-issuance-kit`.
- No admission holds, usage capture, or per-token charging.
- No hosted fiat option — the hosted settlement mechanism is not composed at
  all — no Helm alias, no Arkhai-hosted registry, no webapp.
- No per-token rate card on a published listing.
- No seller installer or packaging beyond the Compose stack.
- No TypeScript or Rust gate.

## Dependencies and Related Changes

- **Depends on** `add-inference-domain-contract` accepted.
- **Consumes** `sign-multi-language-credits-middleware`'s Python signing path
  as it stands; does not wait on its TypeScript and Rust work.
- **Enables** `extract-access-issuance-kit` by supplying the second consumer,
  and `meter-inference-usage` by supplying the stack it changes.
- `repair-storefront-alkahest-configuration` owns the development stack's
  Alkahest readiness; this change's scenario needs it green.
- [`unbacked-listing-publication`](../archive/2026-09-24-unbacked-listing-publication/)
  (archived 2026-09-24) moved the publication hooks a copy of the API-credits
  roles takes and made backing a declared listing property. The copies are taken
  from current `dev`, and inference listings carry the backed value from day one.

## Impact

- New: `domains/inference/{storefront,buyer,service,gateway,model-stub}/`,
  `domains/inference/compose.yml`, `compose.inference.yml`, development
  identities, the e2e scenario and marker.
- Touched: root `docker-compose.yml`, `compose.local-identities.yml`, the
  `e2e-dev-identities-env` target, `domains/Makefile`, root `Makefile`,
  `e2e-tests/pyproject.toml` markers.
- Wire: none beyond the new domain. Database: two new service databases,
  neither shared. Deployment: three new images and one more registry instance
  in the development stack.

## Permanent documentation impact

- [x] `docs/development/ARCHITECTURE.md` — runtime service map and local
      deployment topology gain the inference roles and third registry schema.
- [x] Existing subsystem specification — `market-composition`,
      `deployment-state`, `test-compatibility` scenarios.
- [x] New subsystem specification — `inference` gains the role-composition and
      end-to-end requirements.

## Status

Planned. `design.md` and `tasks.md` are authored against
`add-inference-domain-contract` as implemented and awaiting review;
implementation starts when that change is accepted, and task 1.1 re-checks the
vocabulary against whatever review changed.
