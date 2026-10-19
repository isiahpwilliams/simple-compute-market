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
- **Family vocabulary, `domains/api`** (`arkhai_api`): the names, schemas, and
  identifiers both domains share — the bearer-credential issuance request and
  result with a domain label, the key and grant wire shapes, the fulfillment
  identity and request digest. It depends on foundation kits only, never on a
  domain, and owns no authority or persistence.
- **Family kit, in two distributions.** A base distribution owns what any
  API-selling domain needs: the issuance client, fulfillment orchestration and
  rollback, the evidence projection, the key service and its persistence, the
  authority's shared routes and signed authentication, the gate's authority
  client and request signing, and the storefront-side issuance composition. A
  `credits` distribution owns the prepaid ledger: balances, quantities, quota,
  top-up, and the fixed per-request consumption rule. The credits distribution
  depends on the base; the base never depends on it, so a domain that sells
  access another way installs the base alone. Where the kit lives is an open
  question for the owner and the maintainers; compute's kit sits under
  `provisioning/`, and `kit/` is reserved for family-neutral code.
- **API credits composes the kit.** Its storefront, authority, gate, and buyer
  keep their behaviour, wire, digests, and data, and lose their local
  implementations of everything the kit now owns. This is the risky part of the
  change and lands in slices of one to two thousand lines, each proven by the
  pinned regression tests, the domain's suites, and its end-to-end lane. API
  credits ends as the first thin domain: wiring, controllers, its listing
  schema, and its consumption rule.
- **One digest implementation.** The authority composes the kit's digest and
  identity functions instead of mirroring them, so client and server cannot
  drift. Independent recomputation stays; independent implementation was never
  the point.
- **The contribution surface.** The kit consumes what a domain contributes —
  a listing schema and its publication mapping, publication guards, a
  materialization hook, a consumption rule — and never imports a domain or
  branches on its identity. The inference contract's vocabulary is the second
  consumer that fixes this surface; what it contributes is the inference
  stack's whole domain-specific content.
- **Decide the authority packaging.** Whether an API-selling domain's authority
  is one kit-composed service deployed per domain with its own label, database,
  and key namespace, or a composition root per domain sharing the kit, is
  decided here with both consumers in view.

## Capabilities

### New Capabilities

- `api-family`: the family vocabulary and the family kit's base and credits
  distributions — domain-labelled bearer-credential issuance, stable
  fulfillment identity and request digest, evidence projection and rollback,
  the key authority, the gate's authority client, and the prepaid ledger — and
  what a domain contributes to compose them.

### Modified Capabilities

- `api-credits`: composes the family kit; behaviour, wire, digests, and data
  unchanged, proven by the pinned regression tests.
- `market-composition`: the family-kit rules gain a second family beside
  compute; the extracted-concern rule gains this instance.

## Non-Goals

- No change to any API-credits digest, wire shape, database row, or observable
  behaviour.
- No inference role, stack, or scenario: those compose the kit in
  `compose-inference-domain-stack`.
- No metering, holds, usage capture, or change to the fixed per-request
  consumption rule beyond relocating it.
- No TypeScript or Rust gate changes beyond what relocating the Python client's
  signing requires; their conformance fixture stays where it is and stays
  green.

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

- New: `domains/api/`, the family kit's base and `credits` distributions at
  the directory the design settles, regression fixtures under
  `domains/apicredits/tests/`, `[[domains]]` and family rows in
  `docs/development/ARCHITECTURE.toml`.
- Touched: `domains/apicredits/{settlement,service,storefront,buyer,middleware}`,
  `domains/Makefile`, `kit/Makefile` or the family's, root `Makefile` and
  `tests.yml` target lists, root `dist` ordering, every touched project's
  `pyproject.toml` and lock.
- Wire: none. Database: none. Packaging: new family wheels; the API-credits
  wheels shrink.

## Permanent documentation impact

- [x] `docs/development/ARCHITECTURE.md` — the family-kit section gains the
      `api` family beside compute; the runtime service map and the authority
      boundaries for keys and issuance cite the kit.
- [x] Existing subsystem specification — `api-credits` composition prose;
      `market-composition` family-kit requirements.
- [x] New subsystem specification — `api-family`.

## Status

Design phase. Open for the design: the kit's directory; whether the gate's
authority client ships in the base distribution or in a dependency-light
distribution of its own, which the published middleware's packaging constraint
in `apicredits_middleware/signing.py` motivates; and the authority packaging.
`tasks.md` is authored when the design's review gate passes.
