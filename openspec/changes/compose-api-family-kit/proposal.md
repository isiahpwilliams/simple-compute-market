## Why

API credits and inference sell the same thing: access to an HTTP API, paid for
in advance and delivered as a bearer credential that a gate checks on every
request. What differs between them is what the listing describes and how a
request is priced. Everything else — issuance and its digest, the key service,
the gate's authority client, the storefront's issuance and settlement
composition, the buyer's purchase flow — is the same machinery.

The campaign first planned to copy that machinery into the inference domain and
extract a kit afterwards, once two working consumers showed where the boundary
lay. The copy was carried out as far as the storefront and the authority, and
it answered the question: inference needed roughly 12,500 copied source lines
and added fewer than 300 of its own — a model-card listing builder, a guard
refusing rate cards the stack cannot charge, and a materialization pinning the
rate card at acceptance. There is no boundary to find inside that machinery.
Review of the plan priced the duplication and asked for the alternative the
repository already defines for compute: a family vocabulary package and a family
kit, with each domain reduced to composition wiring, its API controllers, and
the behaviour it alone owns. The copied pull requests were withdrawn unmerged.

This change builds that family. `docs/development/ARCHITECTURE.md` says a
domain with no shared vocabulary beneath it has no family, and names API credits
as the example; a second API-selling domain gives it one. The family is `api`,
not `credits`: credits is one way to pay for API access, and a domain that sold
access by subscription or metered fiat would want the issuance and the gate
without the ledger.

## What Changes

- **Pin API credits first.** Before anything moves, regression tests record the
  exact issuance request digest, fulfillment identity, evidence digest bytes,
  and attestation shapes the API-credits domain produces today for a fixed input
  set. Every later slice is proven byte-identical against them. A failure here
  is a blocking defect, never a migration.
- **The `api` family under `domains/api`.** `ARCHITECTURE.toml` gains the
  family row and both domains join it. The kit lives under the family directory,
  as the scope rule prescribes; compute's kit sits elsewhere only under override
  rows another change owns.
- **Ten projects, each forced by a rule.** The vocabulary `arkhai_api`
  (purchase shape, issuance models, digests, evidence; foundation kits only);
  `contracts` and `client` for the authority's wire models, route contract, and
  typed client; three side libraries whose dependencies the other sides do not
  need — `authority` (key service, ledger, quota-as-capacity composition,
  migrations, route services), `selling` (issuance and settlement composition,
  negotiation adapters, quota listing binding and publication, carriers, route
  services, persistence), and `buying` (buy, negotiate, settle, and listing
  flows); `gate` for the bearer gate; `alkahest` and `arkhai-payments` for the
  mechanism stages; and `service`, the family authority's composition root.
  `design.md` names the rule behind each.
- **API credits composes the kit, slice by slice.** Each slice deletes the
  implementation it replaces, leaves API credits green on its suites and lane,
  and keeps `make check-packaging` green. Behaviour, wire, digests, and data are
  unchanged. API credits ends as the first thin domain: its listing schema and
  kind bindings, its fixed per-request amount as a contribution, its
  configuration, its bindings, compose files, and seed.
- **One digest implementation.** The authority composes the vocabulary's digest
  and identity functions and deletes its own copy, so client and server cannot
  drift.
- **One typed contribution bundle.** A storefront hands `selling` its label,
  kind literals, listing schema and publication mapping, optional guards,
  optional acceptance hook, optional public-result extension, and consumption
  rule; a buyer plugin hands `buying` its schema identity, filters, rendering,
  and commands. The inference contract's purchase-terms module becomes a binding
  of the vocabulary's shape, so the vocabulary has two consumers from its first
  slice.
- **One family authority image.** `domains/api/service` is deployed once per
  domain with its own label, database, key namespace, and identities, and
  accepts route contributions for what metering adds later.
- **The gate relocates under its own name.** `arkhai-api-gate` is the bearer
  gate, httpx-only with identity optional, and the Python reference for the
  conformance trace. `arkhai-apicredits-middleware` is retired from publishing;
  no re-export is kept, because no third party installs it and sellers take the
  pre-built images.

## Capabilities

### New Capabilities

- `api-family`: the family vocabulary and kit — one vocabulary, distributions
  split only where a rule forces it, label-parameterized digests proven
  byte-identical, one typed contribution bundle, one authority service deployed
  per domain, one published gate, kit-owned route services behind
  composition-owned bindings.

### Modified Capabilities

- `api-credits`: composes the family kit with no domain-local copy; behaviour,
  wire, digests, and data unchanged, proven by the pins.
- `market-composition`: the family-kit rules gain a second family beside
  compute, and the extracted-concern rule gains this instance.
- `inference`: its purchase-terms module binds the vocabulary's shape under its
  own kind literal; no promised behaviour changes.

## Non-Goals

- No change to any API-credits digest, wire shape, database row, or observable
  behaviour.
- No inference role, stack, or scenario: those compose the kit in
  `compose-inference-domain-stack`.
- No metering, holds, usage capture, or change to the fixed per-request
  consumption rule beyond relocating it.
- No ledger-free access distribution; deferred in `design.md` with its trigger.
- No TypeScript or Rust gate changes beyond what relocating the Python reference
  requires; their conformance fixture stays where it is and stays green.

## Dependencies and Related Changes

- **Depends on** `add-inference-domain-contract`: the inference vocabulary is
  the second consumer whose contributions fix the kit's surface.
- **Blocks** `compose-inference-domain-stack`, which composes its roles on the
  kit, and through it `meter-inference-usage`, which mutates the kit-composed
  authority once.
- `sign-multi-language-credits-middleware` owns the TypeScript and Rust gates.
- `align-package-paths-with-layers` owns the Alkahest override row the
  API-credits storefront carries today; the kit inherits or retires it, and
  the design says which.

## Impact

- New: `domains/api/` with ten projects — the vocabulary at its root and
  `contracts`, `client`, `authority`, `selling`, `buying`, `gate`, `alkahest`,
  `arkhai-payments`, and `service` beneath it; the pinned regression fixtures
  under `domains/apicredits/tests/`; a `[[families]]` row and two `family`
  attributes in `docs/development/ARCHITECTURE.toml`; a row for the gate in
  `docs/development/RELEASING.md`'s published-packages table and the publish
  workflow, in place of the middleware's, with the gate's one-time PyPI setup
  for a maintainer.
- Touched: every `domains/apicredits` package, which shrinks to bindings and
  its own vocabulary; `domains/apicredits/service` retired in favour of the
  family image; the inference contract's purchase-terms module;
  `domains/Makefile`, the root `Makefile` and `tests.yml` target lists, the
  aggregate kit test target, root `dist` ordering, and every touched project's
  `pyproject.toml` and lock.
- Removed: the `arkhai-apicredits-domain` override row in `ARCHITECTURE.toml`
  and the unmounted issuance-evidence router.
- Wire: none. Database: none; migration identifiers unchanged. Packaging: ten
  new wheels, two of them published; the API-credits wheels shrink and bump.

## Permanent documentation impact

- [x] `docs/development/ARCHITECTURE.md` — the family-kit section gains the
      `api` family beside compute, with the rule that a family's distributions
      split only where a stated rule or dependency weight forces it; the runtime
      service map and the authority-boundaries row for keys and issuance cite
      the family authority.
- [x] `docs/development/RELEASING.md` — the published-packages table replaces
      the middleware's row with the gate's.
- [x] Existing subsystem specification — `api-credits` composition prose and
      its architecture companion's "Implementation composition";
      `market-composition` family-kit requirements.
- [x] New subsystem specification — `api-family`, with an architecture
      companion for the contribution surface and the deferred ledger split.

### Knowledge to promote

- The `api` family, its root, and the rule-derived distribution set —
  `docs/development/ARCHITECTURE.md#family-kits`.
- A family kit splits only where a rule or dependency weight forces it; an
  anticipated split is recorded with its trigger, not built —
  `docs/development/ARCHITECTURE.md#family-kits`.
- The contribution bundle and what each domain supplies —
  `openspec/specs/api-family/architecture.md`.
- Label-parameterized digests and the pin that proves them —
  `openspec/specs/api-family/spec.md`; the API-credits companion's
  "Idempotency boundaries" cites the vocabulary.
- One family authority deployed per domain, with its route-contribution seam —
  `openspec/specs/api-family/spec.md` and `ARCHITECTURE.md`'s runtime service
  map.

## Status

In design; the design is recorded in `design.md` and awaits its design review.
`tasks.md` is authored when that review's gate passes. The slice order the
dependencies impose is in `design.md`.
