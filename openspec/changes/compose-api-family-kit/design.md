# Design

## Context

### What exists

API credits is one domain spread over five distributions, with nothing shared
beneath it. The domain library (`arkhai_apicredits`, about 2,800 source lines)
holds the listing schema, provision terms, negotiation guards, the storefront's
typed authority client with its issuance models and digests, mechanism-neutral
issuance from verified evidence, signed issuance evidence, and the payments
clause validators. The service (`apicredits_service`, about 2,200) holds the
key service, its SQLAlchemy models and hand-rolled migrations, its route
contracts, controllers, and app assembly; it embeds the site and resource-pool
kits and models quota as capacity in the site ledger. The storefront
(`apicredits_storefront`, about 7,700) composes negotiation, settlement, quota
listing binding and publication, issuance evidence persistence, lifecycle loops,
nine routers, and the two seller settlement stages. The buyer plugin
(`arkhai_apicredits_buyer`, about 3,700) holds the buy, negotiate, settle, and
listing flows and the two buyer stages. The published middleware
(`apicredits_middleware`, about 1,200) is the bearer gate, httpx-only with the
identity kit as an optional extra, and the reference implementation of the
cross-language conformance trace under `domains/apicredits/middleware/conformance/`.

Three facts the proposal did not record, found in the code:

- The issuance digest is already implemented twice. The storefront client and
  the service's wire models each spell the same four schema strings and the
  digest domain. The kit does not introduce a mirror; it removes one.
- The authority is also a capacity authority. Quota is a reservation in the
  embedded site ledger, both domains' listings bind to a quota resource in a
  pool, and the service's migrations include the pool and reservation tables.
- Storefront logic lives in the controllers and composition modules, not behind
  framework-free route services. The negotiate controller alone is 289 lines.

One storefront router, the issuance-evidence read, is referenced nowhere and is
never mounted.

### What the inference copy measured

The campaign's earlier plan copied these roles into the inference domain and
extracted a kit afterwards. The copy was carried as far as the storefront and
the authority: about 12,500 copied source lines against fewer than 300 new
ones — a model-card listing builder, a guard refusing rate cards the stack
cannot charge, and a materialization pinning the rate card at acceptance — all
three beside the copy rather than inside it. The shared part is the whole
machinery. The copied pull requests were withdrawn unmerged; the three modules,
the development seed, and the startup refusal of a foreign settlement mechanism
are the inference contribution this design has to admit.

### What governs the design

`docs/development/ARCHITECTURE.md` is a mandate, and its "Package and
dependency layers" and "Family kits" sections decide most of what follows. Each
decision below names the rule that decides it. Where the documents leave a
choice, the decision says so and records the owner's.

## Goals / Non-Goals

**Goals.** One `api` family whose vocabulary and kit every API-selling domain
composes; API credits refactored onto it with its behaviour, wire, digests, and
data unchanged, proven by pinned bytes; a contribution surface the inference
domain fills with its three modules and wiring; the duplicate digest removed.

**Non-Goals.** Any change to an API-credits digest, wire shape, database row,
or observable behaviour. Any inference role, stack, or scenario. Metering,
holds, or usage capture. A TypeScript or Rust gate change beyond what relocating
the Python reference requires. A ledger-free access distribution, deferred under
"Open Questions".

## Decisions

### The family is `api`, rooted at `domains/api`

Credits is one way to pay for API access; a domain selling access by
subscription or by invoice would still publish a listing, issue a credential,
and gate requests on it. The family is named for what is sold, and both domains
join it: `ARCHITECTURE.toml` gains a `[[families]]` row (`name = "api"`,
`directory = "domains/api"`, `vocabulary = "arkhai-api"`) and the `apicredits`
and `inference` domain rows gain `family = "api"`.

The kit lives under the family directory. The scope rule reads scope from the
path: "a package under a family's directory [is scoped] to that family", and the
check classifies any project whose first two path segments are the family
directory that way. Compute's kit sits under `provisioning/` only as a tracked
divergence: each of its five packages carries an override row reading "outside
the family's directory", owned by `align-package-paths-with-layers`. The rules
prescribe `domains/api/`, so no override row is written.

**Rejected:** a function-named top-level directory beside `provisioning/`. It
would need the same override rows compute carries, for a package created after
the rule existed.

### The distributions are the ones the rules force, and no more

`ARCHITECTURE.md` licenses exactly three reasons to split a family's code into
more than one distribution, and each package below exists for one of them.

| Project | Package | Layer, kind | Exists because |
|---|---|---|---|
| `domains/api` | `arkhai_api` | specialization, library | a family vocabulary package "own[s] no authority or persistence, and never depend[s] on a family kit" |
| `domains/api/contracts` | `arkhai_api_contracts` | specialization, contracts | the route-contract pattern: the owning package owns wire models and the route contract, and a `client` may depend only on `contracts`, core, and the identity kit |
| `domains/api/client` | `arkhai_api_client` | specialization, client | the same pattern: a thin client "so a caller does not install the capability's service code to call it", and "the server never depends on its own client" |
| `domains/api/authority` | `arkhai_api_authority` | specialization, library | dependency weight: SQLAlchemy and the site and pool kits, which no storefront or buyer needs |
| `domains/api/selling` | `arkhai_api_selling` | specialization, library | dependency weight: the negotiation runtime, capacity publication, the storefront kit, and the core storefront, which no authority or buyer needs |
| `domains/api/buying` | `arkhai_api_buying` | specialization, library | dependency weight: the buyer core and its configuration, which no storefront or authority needs |
| `domains/api/gate` | `arkhai_api_gate` | specialization, library | dependency weight: embedded in third-party applications, httpx-only, identity optional |
| `domains/api/alkahest` | `arkhai_api_alkahest` | specialization, library, mechanism `alkahest` | the scope rule: "a specialization that knows a mechanism carries the mechanism in its name" |
| `domains/api/arkhai-payments` | `arkhai_api_arkhai_payments` | specialization, library, mechanism `arkhai-payments` | the same |
| `domains/api/service` | `arkhai_api_service` | composition, executable | the family authority's composition root; see below |

Dependencies among them point one way and are acyclic, as the family-kit
section requires: `contracts` → vocabulary; `client` → `contracts`;
`authority`, `selling`, `buying`, `gate` → vocabulary, `contracts`, and (all
but `gate`) `client`; the two mechanism distributions → `selling` and `buying`
plus their mechanism kit; `service` → `authority`. Nothing under `domains/api/`
imports `arkhai_apicredits`, `arkhai_inference`, or any role executable.

`selling` and `buying` are named for the side of the market each serves. They
cannot carry their roles' names: `storefront`, `buyer`, `service`, and `app`
are the role words the check reads as "executable", and these are libraries.

**Rejected:** a base distribution for issuance and keys plus a `credits`
distribution for the ledger. The rule permits a split only where a consumer
"would otherwise install dependencies [it does] not use"; both consumers use
the ledger, and the ledger adds no dependency the authority kit lacks. Deferred
with its trigger under "Open Questions". **Rejected:** one kit distribution for
all three sides, which would install the storefront's publication machinery on
every buyer's machine. **Rejected:** mechanism stages inside `selling` and
`buying` under an override row granting the mechanisms, which is the shape of
the divergence the domain library carries today; "no new dependency of the same
shape should be added while one stands".

### The vocabulary holds what needs no core

A family vocabulary package "depends only on foundation kits, never on a
domain, a role, or core". `arkhai_api` therefore holds, with pydantic and the
identity kit as its only dependencies:

- the purchase shape: a positive integer quantity of credits onto a new key or
  an existing key named by `key_id`, with its payload validation, parameterized
  by the binding domain's kind literal;
- the issuance request and result models, the deterministic fulfillment
  identity, and the issuance request digest, each taking the issuance label as
  an argument;
- the signed, secret-free issuance evidence body, its signing, verification,
  digest, encoding, and the portable fulfillment reference, likewise labelled.

The message, terms, materialization, receipt, and result carriers extend core
schemas, so they cannot be vocabulary. `selling` provides them as base classes
each domain binds to its kind literal. Both domains bind the purchase shape
from the vocabulary: the API-credits terms module and the inference contract's
terms module each become a one-line binding, so the vocabulary has two
consumers from its first slice, which is the "third domain" test applied early.
The inference binding amends `add-inference-domain-contract`'s code under that
change's own kind literal and changes nothing it has promised.

### Contracts and client are thin, and the server never depends on its client

`contracts` holds the authority's wire models — issuance request and response,
consume, verify, adjust, key, grant, and usage shapes — the route contract
naming each route's method, path, signed operation, resource, and admitted
roles, and the operation-name constants. Its package allowlist is the kind
allowlist: core, the identity kit, and the family vocabulary. `client` holds
the typed sync and async client over any transport exposing
`authenticated_request`, built on the contract so request authentication and
the client cannot disagree. The service's own duplicate models and digest
helpers are deleted; it imports the vocabulary's functions, so client and
server recompute the same bytes from one implementation.

### The mechanism stages live in mechanism-named distributions

Each domain role still "MUST declare one immutable table from canonical
mechanism ID to domain-owned stage", and that table stays in the domain's
storefront and buyer compositions, as the wiring it is. The entries move:
`domains/api/alkahest` holds the seller stage, the buyer stage, escrow
selection, and the escrow client helpers; `domains/api/arkhai-payments` holds
the seller stage, the receipt-gated issuance service, the payments clause
validators, and the buyer stage. Each stage takes its collaborators — the
delivery callable, the evidence repository, the private-result repository, the
capacity runtime — as constructor arguments, where today the seller stages read
the storefront's container and settings modules; "instance wiring ... belong[s]
in the composition root". An Alkahest-only storefront installs the first
distribution and not the second.

### The family authority is one service deployed per domain

`domains/api/service` is a composition root at the family root; the scope rule
says "a composition under a family directory composes that family's domains,
which is what makes it a family composition root", and the family-kit section
says a family kit "may own ... authority lifecycles for its family". Compute
is the precedent: "the compute provisioning service is the composition root
that wires them." The service composes `authority`'s key service, ledger,
quota-as-capacity composition, migrations, and route services, binds its
controllers, and takes the issuance label, database, key namespace, signer, and
trusted principals from deployment configuration. Each domain's stack deploys
the one image with its own configuration, as the registry image is deployed
once per schema, satisfying "Deployable stack per market domain".

The service accepts route contributions from a package that "declares their
contracts in its own package and supplies its router as a factory", so a later
inference-only route reaches it without a fork; nothing uses that seam in this
change.

**Rejected:** a composition root per domain. Until metering, the two would
differ only in configuration. **Rejected:** leaving the service under
`domains/apicredits` and letting inference deploy it, which composes a sibling
domain's executable.

### A domain contributes through one typed bundle

"Domains define the values, codecs, hooks, and registrations a family kit
consumes; composition roots select and assemble those contributions", and a
family kit "never discovers or imports its domains". The vocabulary defines a
frozen contribution bundle each storefront's container fills and passes to
`selling`; the buyer plugin fills the buyer bundle for `buying`. Entry points
stay for the role executables only: the plugin groups are for packages
"imported by nobody", and a storefront imports its own domain.

| Field | API credits supplies | Inference supplies |
|---|---|---|
| issuance label | `api-credits` | `inference` |
| kind literals and schema identity | `api_credits.v1`, `api_credits` | `inference.v1`, `inference` |
| listing schema and publication mapping from a quota resource | the named-service listing | the model-card listing |
| publication guards | none | the request-priced guard |
| negotiation-time terms checks | the quota and key guards, from `selling` | the same |
| acceptance hook | none | pin the rate card |
| delivery public-result extension | none | the materialization, beside the connection payload, never the secret |
| consumption rule | a fixed configured amount | the same until metering |
| buyer filters and rendering | service name | model card fields |

Every field a domain may omit is optional in the bundle, so API credits
supplies no placeholder. Each caller — both storefronts, the family service,
each gate, each buyer plugin — composes through the bundle and configuration
alone; the walk found one missing operation, the public-result extension,
which the owner's decision of 2026-10-17 on the stack change requires, and it is
in the table.

### The digest label is a parameter, and the pins come first

The issuance request digest, fulfillment identity, evidence digest, and
portable reference each embed schema strings that today spell API credits. The
vocabulary's functions take the label, and the API-credits binding passes
`api-credits` with its exact existing strings. Before anything moves, a
regression suite under `domains/apicredits/tests/` records, for a fixed input
set, the request digest, the fulfillment identity, the evidence digest, and the
signed attestation shapes the domain produces today; every later slice runs it,
and a difference is a blocking defect. The suite is the change's first
implementation task.

### The gate is the published middleware, relocated

`domains/api/gate` holds the bearer gate: the framework-neutral `TokenGate`,
the ASGI adapter, the configuration, the httpx verify-and-consume client, and
the identity-v2 signing with the identity kit as an optional extra, exactly as
today, parameterized by environment prefix and label. It keeps its own light
HTTP calls rather than depending on `client`, because the published package's
contract is httpx-only. The conformance trace stays at
`domains/apicredits/middleware/conformance/`, owned by
`sign-multi-language-credits-middleware`, and the Python runner replays it
against the relocated gate.

`arkhai-apicredits-middleware` is retired: its row leaves the
published-packages table and the publish workflow, and `arkhai-api-gate` takes
its place with a one-time PyPI setup that is a maintainer's. No re-export under
the old name is kept. There are no third-party sellers installing the package
today, and sellers are expected to take the pre-built images rather than work
at the package layer, so the old name has nothing to protect; a shell would be
a published package with no consumer.

**Rejected:** keeping `arkhai-apicredits-middleware` as a thin re-export of the
gate. The releasing guide permits that form — a declared dependency, nothing
vendored — but it exists only to protect installs nobody has.

### Route services in the kit, bindings in the compositions

The route-contract pattern splits a route into wire models, a route contract, a
typed client, a framework-free route service, and an HTTP binding that
"belongs to whatever composes the process". `selling` and `authority` own the
route services; each domain's storefront, and the family service, own the
bindings. The storefront controllers hold logic today, so the refactor moves
it into route services first and leaves each binding a few lines. The unmounted
issuance-evidence router is dropped, not moved.

### What API credits keeps

Its listing resource schema and kind literals; the meaning of `service_name`;
its fixed per-request amount, supplied as a contribution and configured as
today; its environment prefixes and settings; its settlement tables in both
compositions; its controllers as bindings; its compose files, seed, and
development identities. Its domain library shrinks to the listing schema, the
kind bindings, and the bundle, and its override row in `ARCHITECTURE.toml` is
retired, because the mechanism codecs that earned it move to the mechanism
distributions.

### Slices, each leaving no copy behind

"Every domain that implemented it MUST compose the kit implementation in the
same change, every obsolete domain-local implementation MUST be removed." Each
slice therefore deletes the API-credits implementation it replaces, and no
slice leaves a copy for a later one. Planning fixes the sections; the order the
dependencies impose is: the pins; vocabulary and contracts, with both domains
binding the purchase shape; `client`, with the service composing the shared
digest and deleting its duplicate; `authority` and `domains/api/service`, with
`domains/apicredits/service` retired and the API-credits stack deploying the
family image; `selling`, with the storefront's route services and bindings;
the two mechanism distributions; `gate`, retiring the old distribution; `buying`. Each slice
is one to two thousand lines, leaves API credits green on its suites and its
end-to-end lane, and keeps `make check-packaging` green.

### Compatibility

Wire shapes, digests, database rows, migration identifiers, environment
prefixes do not change. The gate publishes as `arkhai-api-gate`, and the
`arkhai-apicredits-middleware` distribution is no longer published. The API-credits
distributions keep their names and bump versions as their contents shrink. No
database reset is required, and the service's in-process migration chain is
unchanged. `ARCHITECTURE.toml` gains the family row and the two `family`
attributes, loses the domain library's override row, and needs no row for any
new project, because every path reads as intended.

## Risks / Trade-offs

- **Refactoring a live domain.** Mitigated by the pins, each slice's suites and
  lane, and the rule that a slice leaves API credits green. Continuous
  integration does not run on the fork the branches live on; local suites and
  the pins are the evidence until the branches move.
- **Ten projects where there were five.** Each exists for a rule the
  documents state; the cost is lock files and the aggregate test target, which
  `make check-packaging` and "Aggregate kit tests cover every kit" hold.
- **Stages refactored to injection.** The seller stages read composition state
  today; moving them to constructor arguments changes their tests, not their
  behaviour, and the pins cover the bytes they produce.

## Open Questions

- **A ledger-free access distribution.** Splitting `authority` into issuance
  and ledger halves is deferred until a sibling domain sells access without a
  prepaid balance — by subscription, by invoice, or free with a rate limit.
  The trigger is that domain's proposal; the rule that permits the split is
  dependency weight, which such a consumer would create.
- **Inference-only authority routes.** Metering adds hold, settle, and release
  routes the API-credits deployment does not serve. The service's
  route-contribution seam is where they land; whether they ship as a
  contribution from the inference domain or as an optional authority
  distribution is `meter-inference-usage`'s decision.
- **The TypeScript and Rust gates.** They replay the same conformance trace
  and are unaffected by the Python relocation; whether they adopt a family
  name is `sign-multi-language-credits-middleware`'s.

## Migration Plan

No data migration. Each slice is a code relocation proven by the pins; a
deployment upgrades by installing the new wheels. The API-credits stack switches
its authority image to the family service in the slice that retires
`domains/apicredits/service`, with the same database and configuration keys.
Rollback of any slice is reinstalling the previous wheels; no slice writes a
row an earlier version cannot read.
