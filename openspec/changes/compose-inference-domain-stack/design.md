# Design

## Context

`add-inference-domain-contract` shipped the vocabulary: the `inference.v1`
domain contract and its six codecs, the model card and rate card, provision
terms, the usage record and its charge derivation, usage evidence, and the
`inference` filter specification. Nothing composes it. No storefront publishes
a model card, no authority issues a key, nothing stands in front of a model
server, and no buyer command can find or buy one.

This change composes the smallest set of roles that completes one inference
deal on the local development stack. The campaign's sequencing rule, stated in
`add-inference-domain-contract`'s design, governs how: the API-credits issuance
machinery is **copied**, not shared, so that `extract-access-issuance-kit` can
find the shared boundary with two working consumers in view.

### What is copied from

All paths are under `domains/apicredits/`.

| Role | Source | Size |
|---|---|---|
| Seller and buyer semantics | `src/arkhai_apicredits/{listings/reconciler.py, negotiation/{policies,buyer_policies,storefront_round}.py, settlement/{credits_client,fulfillment,issuance_evidence}.py}` | about 2,300 lines |
| Authority | `service/src/apicredits_service/` | about 2,400 lines |
| Storefront | `storefront/src/apicredits_storefront/` | about 6,600 lines |
| Bearer gate | `middleware/python/src/apicredits_middleware/` | about 1,200 lines |
| Buyer plugin | `buyer/src/arkhai_apicredits_buyer/` | about 4,000 lines |
| Gated application | `sample-app/` | the pattern only; the gateway replaces it |

### What inspection found that the proposal did not anticipate

1. **The storefront and buyer copies would carry a hosted-settlement
   dependency.** `apicredits_storefront/settlement_composition.py` and the
   buyer's `buy_cli.py` and `settle_cli.py` compose the hosted fiat mechanism
   beside Alkahest, through `arkhai-kit-hosted-settlement`, which requires a
   separately released client wheel. The campaign excludes a hosted fiat option
   for inference, so a verbatim copy would import a mechanism this domain may
   not offer and a dependency its sellers cannot obtain from a public index.
2. **The contract design assigns authority-side storage of the pinned rate
   card to `meter-inference-usage`,** while this change's proposal said the
   grant row carries it. Adding a column to the copied authority is feature
   work in a frozen copy.
3. **The end-to-end lane runs nightly on a hosted runner** alongside the VM and
   API-credits markets. A CPU vLLM container needs a multi-gigabyte image and a
   model download from an external host on every run.
4. **A per-token rate card cannot be enforced by a per-request gate.** A
   listing that advertises token rates while the gateway charges one credit per
   request would publish a price the seller does not charge.

Each is resolved by a decision below, and the proposal is amended to match.

## Goals / Non-Goals

**Goals**

- One complete inference deal on the local stack through the ordinary buyer
  and seller boundaries: discover by model, negotiate, settle on the
  development chain, receive a key, call the model, exhaust, top up.
- A second working consumer of the issuance machinery, close enough to the
  first that extraction is a comparison and not a reconciliation.
- Role packages that build, test, and install without any separately released
  dependency.

**Non-Goals**

- Per-token charging, admission holds, usage capture, or usage evidence
  emission. `meter-inference-usage` owns them.
- Any change to an API-credits module. The sources are read, never edited.
- A hosted fiat option, a Helm alias, a hosted registry, or a seller installer.
- TypeScript or Rust gates.
- Verifying anything a seller asserts about a model.

## Decisions

### Copies are frozen, and the permitted differences are enumerated

A copied module differs from its source only in ways this section lists. A
difference not listed here is a defect in the copy, and review treats it as
one. This is what keeps extraction a comparison.

**Renames.** Applied mechanically and nowhere else:

| API credits | Inference |
|---|---|
| distribution `arkhai-apicredits-{storefront,service,buyer}` | `arkhai-inference-{storefront,service,buyer}` |
| module `apicredits_storefront`, `apicredits_service`, `arkhai_apicredits_buyer` | `inference_storefront`, `inference_service`, `arkhai_inference_buyer` |
| domain imports `arkhai_apicredits.*` | `arkhai_inference.*` |
| environment prefix `APICREDITS_`, `APICREDITS_STOREFRONT_`, `APICREDITS_MIDDLEWARE_` | `INFERENCE_`, `INFERENCE_STOREFRONT_`, `INFERENCE_GATEWAY_` |
| `arkhai.api-credits.issuance-request.v1`, `…issuance-result.v1` | `arkhai.inference.issuance-request.v1`, `…issuance-result.v1` |
| digest domain label `api-credits` | `inference` |
| `arkhai.api-credits.issuance-evidence.v1`, capability `api-credits.issuance.v1` | `arkhai.inference.issuance-evidence.v1`, `inference.issuance.v1` |
| `arkhai.api-credits.portable-fulfillment-ref.v1` | `arkhai.inference.portable-fulfillment-ref.v1` |
| fulfillment kind `api_credits.v1`, offering mode and provider `api_credits` | `inference.v1`, `inference` |
| key identifier prefix `ak_` | `ik_` |
| buyer command group `market credits` | `market inference` |
| class and function names carrying `ApiCredits`, `api_credit`, `Credits` | the same names carrying `Inference` |

The issuance labels are inside SHA-256 digests on both the client and the
authority. A test pins the digest bytes for a fixed input on each side and
asserts the two agree, so a label that drifts between the copies of the client
and the authority fails a unit test, not a deal.

**Substitutions.** The domain contract, codecs, listing model, pricing
functions, and provision terms come from `arkhai_inference`. Where a copied
module read an API-credits listing field, it reads the model card's equivalent;
the mapping is recorded in `tasks.md` beside the module it applies to.

**Omissions.** Removed from the copies, whole:

- Hosted settlement, per the next decision.
- The legacy issuance path (`LEGACY_ISSUANCE_*` in `keys_model.py` and its
  callers). It exists to read grants written before issuance requests carried a
  schema; no such inference grant can exist.
- Service migrations older than the current schema. The inference authority
  starts at one migration that creates the current tables.

**Additions.** New behaviour lives in new modules, never inside a copied one:
the model-card publication mapping, the request-priced publication guard, the
materialization builder that pins the rate card, the gateway's proxy and model
check, and the buyer's model filters.

The implementation records the source commit each copy was taken from in
`tasks.md`. Until `extract-access-issuance-kit` lands, a change to a copied
API-credits module on `dev` is a decision for that extraction to reconcile; the
recorded commit is what lets it see the drift.

### Alkahest is the only settlement mechanism

The inference storefront registers one mechanism, `alkahest.v1`, and the buyer
plugin composes one. Neither role package depends on
`arkhai-kit-hosted-settlement`.

The copied settlement composition already builds its mechanism clients from a
registry of registrations; the inference registry is constructed with the
Alkahest registration alone. The hosted agreement loader, hosted fulfillment,
hosted projection, hosted routes and controller, and the buyer's hosted
authorization are omitted. A storefront configuration naming any other
mechanism in `[settlement].priority` fails at startup, because the registry
holds no registration to resolve it against.

Three things follow. The campaign's scope decision is enforced by the absence
of code and not by a disabled flag an operator could turn on untested. The role
packages install from the repository's own wheels, which
`package-inference-seller` depends on. And their test jobs need no hosted
release artifact, so they run on a fork's pull request.

Adding a hosted option later is a new registration and its composition in a new
module, under its own change.

**Alternative rejected:** copy the hosted composition and leave it disabled by
configuration. It keeps the copy closer to its source, but ships a reachable,
untested payment path in a domain scoped not to have one, and makes every
inference role depend on a wheel a third-party seller cannot install. Hosted
composition is also not among the modules the extraction moves.

### The gate is internal to the gateway

API credits ships its bearer gate as a middleware distribution for sellers to
embed in their own applications. An inference seller's deliverable is the
gateway itself, so the gate is copied into the gateway package as
`inference_gateway.gate` and is not a distribution of its own. What extraction
later moves into kit — the authority client and request signing — is the same
in either packaging.

### The rate card is pinned in the materialization; the authority is unchanged

On issuance the storefront builds an `InferenceMaterialization` carrying the
rate card of the listing the accepted negotiation was made against, read from
the storefront's own stored listing at acceptance and not re-read at
fulfillment. The buyer receives it with the key. The invariant the contract
states — credits consume at the rate the buyer saw when paying — therefore has
a durable, seller-signed record from the first deal.

The authority's grant row is not extended. Storing the card where the
consumption path reads it is `meter-inference-usage`'s work, done once against
the kit-composed authority, as the contract design already says. The proposal's
"grant row carrying the pinned rate card" is withdrawn.

Consequence for `meter-inference-usage`: grants issued by this stack have no
authority-side card. That change either carries the card on the issuance
request from then on and treats earlier development grants as request-priced,
which the next decision makes true of every one of them, or requires a stack
reset. It is a development-stack concern; no seller is running this stack.

### Only request-priced rate cards are publishable until metering lands

The copied gate charges a fixed amount when it admits a request. For a rate
card whose token and image rates are zero and whose `request_credits` is `N`,
the contract's `derive_charge` yields exactly `N` for every successful request.
So a flat per-request charge is the *correct* charge for a request-priced card,
and wrong for any other.

The storefront therefore refuses to publish a listing whose rate card has a
non-zero prompt, cached-prompt, completion, or image rate, naming the field,
and the gateway is configured with the published `request_credits` as its
amount per request. The development listing is priced at one credit per
request. A per-token card becomes publishable when `meter-inference-usage`
removes this guard.

This keeps the stack honest. Without the guard, the registry would index a
per-token price that nothing enforces, and a buyer comparing listings by token
rate would be comparing numbers the sellers do not charge.

One divergence from the contract remains and is accepted for this change: the
gate charges on admission, so a request the model server then fails is still
charged, where `derive_charge` gives a failed request zero. Releasing a charge
needs the hold-and-settle path that metering adds. It is recorded under risks.

### The gateway's surface

`arkhai-inference-gateway` is an ASGI application in front of one model server.

- `POST /v1/chat/completions` and `POST /v1/completions` are gated and
  proxied. Every other path is `404`, except the two below.
- `GET /v1/models` returns only the models the gateway is configured to serve,
  and `GET /health` reports liveness. Both are ungated: the model list is
  already public in the listing, and the copied gate has no verify-without-
  charge path to gate it with.
- **The model is checked before the charge.** The request body is read up to a
  configured limit and its `model` must equal a configured
  `served_model_name`; otherwise the gateway answers `404` with an OpenAI-style
  `model_not_found` error and no credit is spent. A body over the limit is
  `413`; a body that is not a JSON object is `400`. The check sits outside the
  gate so that a refused request never reaches it.
- **The buyer's credential stops at the gateway.** The `Authorization` header
  is removed before proxying. If the model server requires a credential of its
  own, the gateway sends one from a mounted file. Hop-by-hop headers are
  removed in both directions.
- **Streaming is passed through unbuffered.** A server-sent-event response is
  forwarded chunk by chunk as it arrives. Nothing reads its `usage` yet.
- A model-server error is passed through with its status. An unreachable or
  timed-out model server is `502` or `504`.
- A drained key receives the gate's `402`, whose body points at the storefront
  and registry where more credits can be bought; a missing or unknown key is
  `401`; a revoked key is `403`. These are the copied gate's behaviour.

The gateway signs its authority requests as the `service` role with its own
Ed25519 credential and verifies the authority's signed responses, exactly as
the API-credits gated application does.

### The development model server is a deterministic stub; vLLM is a profile

The default stack's model server is `arkhai:inference-model-stub`: a small
OpenAI-compatible server in `domains/inference/model-stub/` that answers chat
completions and completions deterministically, reports `usage`, and streams
server-sent events with a final usage chunk when asked. It follows the
API-credits sample application's precedent of a minimal in-repository
application standing in for what the seller really runs.

A `vllm` Compose profile replaces it with the CPU vLLM image and a small
instruct model for anyone who wants a real model locally. The profile is not
part of the end-to-end lane.

The thing under test is the market plumbing and the gateway, not a model
server. A stub makes the scenario deterministic, keeps the nightly lane free of
a multi-gigabyte pull and an external model download, and lets the scenario
assert exact response bodies. `qualify-inference-market` owns proving the
gateway against real vLLM, where streaming, cancellation, and usage fidelity
are what is being qualified. The proposal's "the model server is the CPU vLLM
image" is amended accordingly.

### Stack topology and development identities

`domains/inference/compose.yml` defines five services, following the
API-credits file's conventions:

| Service | Image | Host port | State |
|---|---|---|---|
| `inference-registry` | `arkhai:registry`, selecting the `inference` filter specification | 8100 | registry volume conventions |
| `inference-service` | `arkhai:inference-service` | 8102 | `inference-service-data` |
| `inference-model` | `arkhai:inference-model-stub` | none | none |
| `inference-gateway` | `arkhai:inference-gateway` | 8105 | none |
| `inference-storefront` | `arkhai:inference-storefront` | 8103 | `inference-storefront-data` |

The authority and the storefront each own a database on their own volume;
neither is shared with the other or with any API-credits service.
`compose.inference.yml` at the repository root is the standalone wrapper over
`compose.dev.yml`, and the root `docker-compose.yml` includes the domain file so
the full stack carries all three markets. Identity bindings go in
`compose.local-identities.yml`, because an including file cannot redefine an
included service.

Development identities under `dev-env/identities/`, each a well-known
deterministic development value documented in that directory's README:

| File | Role | Variable |
|---|---|---|
| `inference-registry.ed25519` | registry authority | `INFERENCE_REGISTRY_IDENTITY_CREDENTIAL_FILE` |
| `inference-service.ed25519` | authority's signing credential | `INFERENCE_SERVICE_IDENTITY_CREDENTIAL_FILE` |
| `inference-gateway.ed25519` | gateway, `service` role | `INFERENCE_GATEWAY_IDENTITY_CREDENTIAL_FILE` |
| `inference.identity.env`, `inference.wallet.env` | storefront, `seller` role, Anvil development account 8 | `INFERENCE_IDENTITY_ENV_FILE`, `INFERENCE_EVM_WALLET_ENV_FILE` |
| `inference-admin-key` | administrative credential mount | `INFERENCE_ADMIN_KEY_FILE` |

Account 8 is unassigned in the existing table, so the inference seller shares a
principal with no other role. `e2e-dev-identities-env` prints the six
variables. The authority's trusted principals and the gateway's and
storefront's expected authorities are pinned to the public halves, as the
API-credits stack pins its own.

### Publication and the development listing

Publication follows the API-credits path: the listing names a
`capacity_site_id` and a quota `resource_id` in the authority's ledger, the
reconciler closes the listing at zero and reopens it when quota is added, and
issuance commits quota through an open-ended reservation. Backing is declared
with the backed value.

The storefront's `[seed]` block gains the model-card fields and, on a fresh
stack, registers the quota resource and publishes one listing whose endpoint is
the gateway: a small instruct model identifier, `provenance = "self-hosted"`,
`quantization = "none"`, a rate card of one credit per request, and a quota
large enough that the scenario cannot close the listing. `model_id` is derived
with the contract's `derive_model_id` from the configured owner and name.

### The buyer plugin

`arkhai-inference-buyer` registers under `market.buyer_domains` and contributes
`market inference listing list|show`, `buy`, `negotiate`, `settle`, and
`settlement status`. It declares the `inference` schema identity, so its
discovery reaches only registries declaring it.

Listing filters are compiled from the served filter specification, as
`registry-discovery` requires: model, model family, quantization, modality,
supported parameter, provenance, minimum context length, and the two rate
bounds. A rate bound without a settlement asset is refused before any request
is sent, because the served specification declares the co-requirement; the
plugin encodes no pairing rule of its own. A completed purchase prints the key,
the gateway base URL, and the served model name — what a client needs to make
its first request.

### The end-to-end scenario

`e2e_inference_deal` is one scenario through the shared domain-neutral
helpers, in the same lane as the VM and API-credits scenarios:

1. Discover the listing by `model_id` on the inference registry.
2. Negotiate a new key and settle on the development chain.
3. Assert the materialization carries the listing's rate card.
4. Call `POST /v1/chat/completions` with the issued key and assert the stub's
   exact response.
5. Call it with an unlisted `model` and assert `404` and an unchanged balance.
6. Consume to `402` and assert the body's purchase pointer.
7. Buy again into the existing key and assert a call succeeds.
8. Stream one completion and assert the events arrive in order.

It asserts the buyer's schema filter leaves the compute and API-credits
registries alone, as the API-credits scenario does for its own.

### Distributions, images, and targets

| Distribution | Path | Version | Console script or entry point |
|---|---|---|---|
| `arkhai-inference-domain` | `domains/inference/` | 0.2.0 | gains the seller and buyer semantics above |
| `arkhai-inference-service` | `domains/inference/service/` | 0.1.0 | `inference-service` |
| `arkhai-inference-storefront` | `domains/inference/storefront/` | 0.1.0 | `inference-storefront`; `market.storefront_domains: inference` |
| `arkhai-inference-gateway` | `domains/inference/gateway/` | 0.1.0 | `inference-gateway` |
| `arkhai-inference-model-stub` | `domains/inference/model-stub/` | 0.1.0 | `inference-model-stub` |
| `arkhai-inference-buyer` | `domains/inference/buyer/` | 0.1.0 | `market.buyer_domains: inference` |

Every project follows the converged layout: `src/<package>`, a lock managed
through `scripts/uv_project.py`, a `Makefile` whose `reinit` and `test` match
the other domains, and an image built from the repository wheelhouse. Targets:
`dist-inference-{service,storefront,gateway,model-stub,buyer}`,
`build-inference-{service,storefront,gateway,model-stub}`, and
`test-inference-{service,storefront,gateway,buyer}`, joined to the `dist`,
`build`, and `test` aggregates. The four images join `make build`; the proposal
said three, before the stub existed. Each tested project gets a test-matrix row
with no hosted-release requirement.

### Landing in reviewable slices

The change is about 17,000 lines, most of it copied. It lands as stacked pull
requests, one per section of `tasks.md`, each green on its own:

1. Domain-package semantics and the authority.
2. The storefront.
3. The gateway and the model stub.
4. The buyer plugin.
5. The stack, identities, targets, and the end-to-end scenario; closeout.

A copied module's pull request states the source commit and shows the diff
against its source after renames, so a reviewer reads the differences and not
the copy.

## Risks / Trade-offs

- **Seventeen thousand lines of transient duplication.** Accepted by the
  campaign's sequencing rule. Bounded by the frozen-copy rule, the enumerated
  differences, the recorded source commit, and `extract-access-issuance-kit`'s
  requirement that no domain-local copy survives.
- **Source drift during the window.** An API-credits fix on `dev` after the
  copy is taken is not in the inference copy. The recorded commit makes the
  drift visible; a security fix is ported by hand and noted in `tasks.md`.
- **A failed request is charged.** The gate charges on admission. Closed by
  `meter-inference-usage`'s hold, settle, and release.
- **Request-priced only.** No seller can publish a per-token price until
  metering lands. That is the honest state of the stack and is why
  `package-inference-seller` depends on metering.
- **The stub is not a model server.** The scenario proves the gateway's
  contract with an OpenAI-compatible upstream, not vLLM's behaviour.
  `qualify-inference-market` owns that.
- **The model check buffers the request body.** Bounded by a configured limit.
  A prompt larger than the limit is refused, not truncated.
- **A heavier nightly lane.** Five more containers, none large. The lane's
  memory limits follow the API-credits services'.

## Open questions

Each carries its revisit trigger. None is prescribed by a task in this change.

1. **Whether `GET /v1/models` should require a key.** Trigger: a seller whose
   catalogue is not public, or a verify-without-charge path on the authority,
   which metering introduces.
2. **Whether the vLLM profile belongs in a scheduled lane.** Owned by
   `qualify-inference-market`.
3. **Whether the gateway should serve more than one model server.** Trigger: a
   seller running several. One listing is one served model either way; this is
   only about how many upstreams one gateway process fronts.

## Migration Plan

Additive. No existing service, wire shape, database, or distribution changes;
`arkhai-inference-domain` gains modules under a minor version. The root stack
gains five services, so a contributor's `docker compose up` starts them once
the images are built. Rollback is removing the include from
`docker-compose.yml` and the new directories; no other domain reads anything
this change writes.
