## ADDED Requirements

### Requirement: The api family shares one vocabulary and one kit

The `api` family's vocabulary — the purchase shape, the issuance request and
result, the fulfillment identity and request digest, and the issuance evidence —
MUST live once, in the family vocabulary package under `domains/api`, and every
API-selling domain MUST bind it rather than define or copy its own. The
vocabulary MUST depend only on foundation kits, never on core, a domain, a role,
or a family-kit distribution. No distribution under `domains/api` MUST import an
API-selling domain or a role executable.

#### Scenario: Two domains bind the purchase shape

- **WHEN** the API-credits and inference domains each construct provision terms
  for three credits onto a new key
- **THEN** both validate the payload through the vocabulary's one definition,
  differing only in the kind literal each binds

#### Scenario: A family package imports a domain

- **WHEN** the architecture check reads an import of `arkhai_apicredits` or
  `arkhai_inference` from any project under `domains/api`
- **THEN** the check fails naming the import, and no exception row excuses it

### Requirement: Family kit distributions exist only where a rule forces them

The family kit MUST be split into distributions only where the scope rule, the
route-contract pattern, or dependency weight requires it: a `contracts` package
for wire models and the route contract, a `client` package for the typed client,
one library per market side — authority, selling, buying — whose dependencies
the other sides do not need, one library for the bearer gate, and one library
per settlement mechanism carrying that mechanism's name. Dependencies among
them MUST be acyclic and point from mechanism libraries to the side libraries,
from side libraries to `client`, `contracts`, and the vocabulary, and from
`client` to `contracts`.

#### Scenario: A buyer plugin is installed

- **WHEN** a domain's buyer plugin and its dependencies are installed
- **THEN** the environment contains the buying library and no capacity
  publication, storefront shell, or SQLAlchemy model from the selling or
  authority libraries

#### Scenario: An Alkahest-only storefront is installed

- **WHEN** a storefront composes only the `alkahest.v1` stage entries
- **THEN** its environment contains the family's Alkahest library and not its
  Arkhai payments library

### Requirement: Issuance digests are label-parameterized and byte-identical

The vocabulary's request digest, fulfillment identity, evidence digest, and
portable fulfillment reference MUST take the issuance label as an argument and
MUST produce, for the label `api-credits`, exactly the bytes the API-credits
domain produced before composing the kit. The authority MUST compute those
values through the vocabulary's functions and MUST NOT keep an implementation
of its own.

#### Scenario: The API-credits pins are replayed

- **WHEN** the pinned regression inputs are digested through the vocabulary with
  the label `api-credits`
- **THEN** every recorded request digest, fulfillment identity, evidence digest,
  and attestation shape matches byte for byte

#### Scenario: Two labels digest the same request

- **WHEN** one issuance request is digested under `api-credits` and under
  `inference`
- **THEN** the two digests differ, and each authority accepts only its own

### Requirement: A domain contributes through one typed bundle

A storefront composition root MUST hand the selling library one frozen
contribution bundle naming the domain's issuance label, kind literals and
schema identity, listing schema and publication mapping, optional publication
guards, optional acceptance hook, optional delivery public-result extension,
and consumption rule; a buyer plugin MUST hand the buying library a bundle
naming its schema identity, filters, rendering, and commands. The kit MUST
treat every optional field's absence as valid and MUST NOT discover or import a
domain to obtain a contribution.

#### Scenario: A domain omits every optional contribution

- **WHEN** the API-credits storefront composes the selling library with no
  guard, no acceptance hook, and no public-result extension
- **THEN** publication, acceptance, and delivery run with the kit's defaults and
  no placeholder implementation is supplied

#### Scenario: A domain extends the public result

- **WHEN** a storefront's bundle supplies a public-result extension and a
  delivery completes
- **THEN** the delivery's public result carries the extension beside the
  connection payload and never the bearer secret

### Requirement: The family authority is one service deployed per domain

The family MUST provide one authority service composition root under
`domains/api/service` that composes the authority library and takes its
issuance label, database, key namespace, signer, and trusted principals from
deployment configuration. Each API-selling domain's stack MUST deploy that
image with its own configuration and MUST NOT share a database or key namespace
with another domain's deployment. The service MUST accept route contributions
declared in a contributing package and supplied as a router factory.

#### Scenario: Two domains deploy the authority

- **WHEN** the API-credits and inference stacks each start the family service
  with their own label, database, and signer
- **THEN** a key issued under one label is unknown to the other deployment, and
  each deployment's issuance digests carry its own label

#### Scenario: A route contribution is mounted

- **WHEN** a package declares an authority route contract and supplies its
  router factory to the service's composition
- **THEN** the service mounts it behind its authentication, and every mounted
  route resolves to exactly one contract

### Requirement: The bearer gate is one published family package

The bearer gate — the framework-neutral gate, its ASGI adapter, its
configuration, its verify-and-consume client, and its optional identity
signing — MUST live in one family library whose runtime dependencies are httpx
alone, with the identity kit as an optional extra, parameterized by
environment prefix and label. The Python gate MUST remain the reference
implementation that replays the cross-language conformance trace. The gate
MUST be published under its own distribution name, and the repository MUST NOT
publish a second distribution carrying the same code under another name.

#### Scenario: The published packages are listed

- **WHEN** the published-packages table and the publish workflow are read
- **THEN** the gate library appears once, under its own name, and no
  API-credits-named middleware distribution appears

#### Scenario: The conformance trace is replayed

- **WHEN** the Python conformance runner replays the recorded session against
  the relocated gate
- **THEN** every step's decision, error code, purchase pointer, and
  collaborator call counts match the trace

### Requirement: Route services are kit-owned and bindings are composition-owned

Each route the selling or authority library serves MUST have a framework-free
route service in that library that validates and performs the route and reports
refusals as errors carrying a status code, and an HTTP binding in the
composition that mounts it — a domain's storefront or the family service. A
binding MUST hold no business logic beyond mapping the route to its service and
its error to a response.

#### Scenario: A storefront binds the negotiate route

- **WHEN** the API-credits storefront mounts its negotiate route
- **THEN** the controller delegates every decision to the selling library's
  route service, and the same service serves the inference storefront's binding
