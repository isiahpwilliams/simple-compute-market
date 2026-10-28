## ADDED Requirements

### Requirement: A gateway in front of a model server is one family library

The family MUST provide one gateway library that fronts an OpenAI-style model
server behind the bearer gate. It consumes one family-owned offering value
— the service name it admits, a default per-request charge, the purchase
pointer, the upstream and its credential reference, and an opaque
verification input — which the composing domain's executable projects from
its own validated listing; the library MUST import no domain and MUST NOT
read a listing itself. It reads the request's `model` and refuses one the
offering does not serve before any charge; it verifies the key, calls a
per-request verification hook with the offering's verification input and the
key's accepted terms digest, which admits everything until a proof format is
configured, and only then charges the key's verified charge, or the
offering's default when verification returns none, and forwards; it replaces
the buyer's credential with the deployment's own upstream credential,
forwards streamed responses as they arrive, and lists only the served model.

#### Scenario: Two domains front model servers

- **WHEN** the inference gateway executable and an API-credits composition each
  wrap a model server with the library
- **THEN** both refuse an unlisted model uncharged, charge an admitted request
  once, and stream, differing only in the values each root supplies

#### Scenario: A domain is imported by the library

- **WHEN** the architecture check reads an import of a domain package from the
  gateway library
- **THEN** the check fails naming the import

#### Scenario: The seller reprices after a sale

- **WHEN** a key was issued under a listing charging one credit per request,
  the seller republishes the listing at ten, and the gateway is restarted
- **THEN** requests on that key are charged one credit, a key issued after the
  republication is charged ten, and a top-up of the first key from the
  repriced listing is refused

### Requirement: The gate verifies and charges in separable steps

The bearer gate MUST expose key verification separately from the charge, with
the same authority exchanges and cached state as its single authorize
operation, so a composition can run a check between a verified key and its
charge without charging a request it then refuses.

#### Scenario: A check between verification and charge refuses

- **WHEN** a composition verifies a key, runs its own check, and refuses
- **THEN** the key's balance is unchanged and the authority saw only the
  verification

### Requirement: The issuance subject may carry accepted terms

The family issuance subject MAY carry a terms digest and a per-request charge
that the domain's projection reads from the accepted listing. When present,
both MUST enter the issuance request digest and the signed evidence, the
authority MUST record them on the grant, and `verify` MUST return the key's
pinned values; when absent, digests, evidence, and `verify` MUST be
byte-identical to their form before the fields existed.

#### Scenario: API credits issues without terms

- **WHEN** an API-credits issuance request, which sets neither value, is
  digested and its key verified
- **THEN** the digest, the evidence, and the verify response match the
  recorded pins byte for byte

### Requirement: A key is scoped to its first grant

The authority MUST bind a key to the service, resource, and accepted terms
digest of the grant that created it and MUST refuse an existing-key issuance
whose service, resource, or terms differ, naming the refusal, so a key's one
balance is only ever spent on what every one of its grants bought, at the
charge each was bought at.

#### Scenario: A key is topped up from another listing

- **WHEN** a buyer who holds a key issued for one listing purchases onto that
  key from a listing with a different service or resource
- **THEN** issuance is refused naming the key's scope, no grant is recorded,
  and the key's balance is unchanged
